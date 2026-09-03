import time
from dataclasses import dataclass, field
from typing import Any

from app.exceptions import GuardrailFailureCategory
from app.schemas import QueryTokenUsage
from app.services.query_agent import LangChainQueryAgent, QueryAgentResult
from app.services.query_guardrails import AfterGuardrail

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class AttemptRecord:
    attempt_number: int
    sql_query: str
    passed: bool
    failure_category: GuardrailFailureCategory | None
    failure_detail: str | None
    token_usage: QueryTokenUsage
    tool_calls: list[dict[str, Any]]
    latency_ms: int


@dataclass(frozen=True)
class GenerationOutcome:
    success: bool
    sql_query: str | None
    generation_result: QueryAgentResult | None
    attempts: list[AttemptRecord] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def repaired(self) -> bool:
        return self.success and self.attempt_count > 1

    @property
    def total_token_usage(self) -> QueryTokenUsage:
        total_tokens = sum(attempt.token_usage.total_tokens for attempt in self.attempts)
        input_tokens = sum(attempt.token_usage.input_tokens for attempt in self.attempts)
        output_tokens = sum(attempt.token_usage.output_tokens for attempt in self.attempts)
        cached_input_tokens = sum(
            attempt.token_usage.cached_input_tokens for attempt in self.attempts
        )
        return QueryTokenUsage(
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        )


class QueryRepairLoop:
    """Coordinates the generate -> after-guardrail -> repair cycle.

    Attempt 1 is the initial generation; attempts 2+ are repairs fed the
    prior SQL and the exact guardrail failure. Execution never happens until
    an attempt passes the after guardrail, or attempts are exhausted.
    """

    def __init__(
        self,
        query_agent: LangChainQueryAgent,
        after_guardrail: AfterGuardrail,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self._query_agent = query_agent
        self._after_guardrail = after_guardrail
        self._max_attempts = max_attempts

    def run(
        self,
        question: str,
        metadata_json: dict[str, Any],
        last_user_question: str | None = None,
        last_sql_query: str | None = None,
    ) -> GenerationOutcome:
        attempts: list[AttemptRecord] = []
        generation_result: QueryAgentResult | None = None
        previous_sql: str | None = None
        failure_category: GuardrailFailureCategory | None = None
        failure_detail: str | None = None

        for attempt_number in range(1, self._max_attempts + 1):
            started_at = time.monotonic()
            if attempt_number == 1:
                generation_result = self._query_agent.generate_sql(
                    question=question,
                    metadata_json=metadata_json,
                    last_user_question=last_user_question,
                    last_sql_query=last_sql_query,
                )
            else:
                generation_result = self._query_agent.repair_sql(
                    question=question,
                    metadata_json=metadata_json,
                    previous_sql=previous_sql,
                    failure_category=failure_category,
                    failure_detail=failure_detail,
                    last_user_question=last_user_question,
                    last_sql_query=last_sql_query,
                )
            latency_ms = int((time.monotonic() - started_at) * 1000)

            guardrail_result = self._after_guardrail.check(
                generation_result.sql_query,
                metadata_json=metadata_json,
            )

            attempts.append(
                AttemptRecord(
                    attempt_number=attempt_number,
                    sql_query=generation_result.sql_query,
                    passed=guardrail_result.passed,
                    failure_category=guardrail_result.failure.category
                    if guardrail_result.failure
                    else None,
                    failure_detail=guardrail_result.failure.detail
                    if guardrail_result.failure
                    else None,
                    token_usage=generation_result.token_usage,
                    tool_calls=generation_result.tool_calls,
                    latency_ms=latency_ms,
                )
            )

            if guardrail_result.passed:
                return GenerationOutcome(
                    success=True,
                    sql_query=guardrail_result.sql_query,
                    generation_result=generation_result,
                    attempts=attempts,
                )

            previous_sql = generation_result.sql_query
            failure_category = guardrail_result.failure.category
            failure_detail = guardrail_result.failure.detail

        return GenerationOutcome(
            success=False,
            sql_query=None,
            generation_result=generation_result,
            attempts=attempts,
        )
