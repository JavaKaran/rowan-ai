from dataclasses import dataclass
from typing import Any

from app.exceptions import GuardrailFailureCategory, UnsafeSQLQuery
from app.services.query_validator import ReadOnlySQLValidator


@dataclass(frozen=True)
class AfterGuardrailFailure:
    category: GuardrailFailureCategory
    detail: str


@dataclass(frozen=True)
class AfterGuardrailResult:
    sql_query: str | None
    failure: AfterGuardrailFailure | None

    @property
    def passed(self) -> bool:
        return self.failure is None

    @classmethod
    def ok(cls, sql_query: str) -> "AfterGuardrailResult":
        return cls(sql_query=sql_query, failure=None)

    @classmethod
    def blocked(cls, category: GuardrailFailureCategory, detail: str) -> "AfterGuardrailResult":
        return cls(sql_query=None, failure=AfterGuardrailFailure(category=category, detail=detail))


class BeforeGuardrail:
    """Screens the incoming natural language request before agent execution.

    Blocks prompt injection and write-intent requests by raising immediately —
    a blocked request must never reach the agent.
    """

    def __init__(self, validator: ReadOnlySQLValidator | None = None):
        self._validator = validator or ReadOnlySQLValidator()

    def check(self, question: str) -> str:
        return self._validator.validate_user_request(question)


class AfterGuardrail:
    """Enforces read-only, schema-aware SQL safety on generated candidates.

    Never raises for guardrail violations — callers (the repair loop) need a
    typed, inspectable failure to feed back into the agent instead of an
    exception that ends the request.
    """

    def __init__(self, validator: ReadOnlySQLValidator | None = None):
        self._validator = validator or ReadOnlySQLValidator()

    def check(
        self,
        sql_text: str,
        metadata_json: dict[str, Any] | None = None,
    ) -> AfterGuardrailResult:
        try:
            validated_sql = self._validator.validate(sql_text, metadata_json=metadata_json)
        except UnsafeSQLQuery as exc:
            category = exc.category or GuardrailFailureCategory.DISALLOWED_KEYWORD
            return AfterGuardrailResult.blocked(category, str(exc))

        return AfterGuardrailResult.ok(validated_sql)
