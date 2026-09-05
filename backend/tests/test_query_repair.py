import unittest

from app.exceptions import (
    AgentRecursionLimitExceeded,
    GuardrailFailureCategory,
    SQLGenerationTimedOut,
)
from app.schemas import QueryTokenUsage
from app.services.query_guardrails import AfterGuardrail
from app.services.query_repair import QueryRepairLoop

METADATA = {
    "schemas": [
        {
            "name": "public",
            "tables": [{"name": "users"}],
        }
    ]
}


class FakeQueryAgent:
    def __init__(self, generate_sql_result, repair_results=None):
        self.generate_sql_result = generate_sql_result
        self.repair_results = list(repair_results or [])
        self.generate_calls = []
        self.repair_calls = []

    def generate_sql(self, question, metadata_json, last_user_question=None, last_sql_query=None):
        self.generate_calls.append(
            {
                "question": question,
                "metadata_json": metadata_json,
                "last_user_question": last_user_question,
                "last_sql_query": last_sql_query,
            }
        )
        return self.generate_sql_result

    def repair_sql(
        self,
        question,
        metadata_json,
        previous_sql,
        failure_category,
        failure_detail,
        last_user_question=None,
        last_sql_query=None,
    ):
        self.repair_calls.append(
            {
                "question": question,
                "metadata_json": metadata_json,
                "previous_sql": previous_sql,
                "failure_category": failure_category,
                "failure_detail": failure_detail,
                "last_user_question": last_user_question,
                "last_sql_query": last_sql_query,
            }
        )
        return self.repair_results.pop(0)


class RaisingQueryAgent:
    """A FakeQueryAgent-alike whose generate_sql/repair_sql can raise mid-loop."""

    def __init__(self, generate_sql_result=None, generate_sql_error=None, repair_results=None):
        self.generate_sql_result = generate_sql_result
        self.generate_sql_error = generate_sql_error
        self.repair_results = list(repair_results or [])
        self.repair_calls = []

    def generate_sql(self, question, metadata_json, last_user_question=None, last_sql_query=None):
        if self.generate_sql_error is not None:
            raise self.generate_sql_error
        return self.generate_sql_result

    def repair_sql(
        self,
        question,
        metadata_json,
        previous_sql,
        failure_category,
        failure_detail,
        last_user_question=None,
        last_sql_query=None,
    ):
        self.repair_calls.append(previous_sql)
        result = self.repair_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_generation_result(sql_query, total_tokens=10, tool_calls=None):
    from types import SimpleNamespace

    return SimpleNamespace(
        sql_query=sql_query,
        summary="a summary",
        token_usage=QueryTokenUsage(
            total_tokens=total_tokens,
            input_tokens=total_tokens - 2,
            output_tokens=2,
            cached_input_tokens=0,
        ),
        provider="groq",
        model_name="test-model",
        tool_calls=tool_calls if tool_calls is not None else [],
    )


class QueryRepairLoopTest(unittest.TestCase):
    def setUp(self):
        self.after_guardrail = AfterGuardrail()

    def test_succeeds_on_first_attempt_without_calling_repair(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users LIMIT 10")
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.sql_query, "SELECT id FROM users LIMIT 10")
        self.assertEqual(outcome.attempt_count, 1)
        self.assertFalse(outcome.repaired)
        self.assertEqual(agent.repair_calls, [])

    def test_repairs_after_first_attempt_fails_guardrail(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users"),
            repair_results=[make_generation_result("SELECT id FROM users LIMIT 10")],
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertTrue(outcome.success)
        self.assertEqual(outcome.sql_query, "SELECT id FROM users LIMIT 10")
        self.assertEqual(outcome.attempt_count, 2)
        self.assertTrue(outcome.repaired)
        self.assertEqual(len(agent.repair_calls), 1)
        self.assertEqual(agent.repair_calls[0]["previous_sql"], "SELECT id FROM users")
        self.assertEqual(
            agent.repair_calls[0]["failure_category"],
            GuardrailFailureCategory.MISSING_LIMIT,
        )
        self.assertIn("LIMIT", agent.repair_calls[0]["failure_detail"])

    def test_exhausts_three_attempts_and_reports_failure(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users"),
            repair_results=[
                make_generation_result("SELECT id FROM users"),
                make_generation_result("SELECT id FROM users"),
            ],
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertFalse(outcome.success)
        self.assertIsNone(outcome.sql_query)
        self.assertEqual(outcome.attempt_count, 3)
        self.assertEqual(len(agent.repair_calls), 2)
        self.assertEqual(
            outcome.attempts[-1].failure_category,
            GuardrailFailureCategory.MISSING_LIMIT,
        )

    def test_sums_token_usage_across_all_attempts(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users", total_tokens=10),
            repair_results=[
                make_generation_result("SELECT id FROM users LIMIT 10", total_tokens=15),
            ],
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertEqual(outcome.total_token_usage.total_tokens, 25)

    def test_stops_repairing_after_max_attempts_override(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users"),
            repair_results=[make_generation_result("SELECT id FROM users")],
        )
        loop = QueryRepairLoop(
            query_agent=agent,
            after_guardrail=self.after_guardrail,
            max_attempts=2,
        )

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertFalse(outcome.success)
        self.assertEqual(outcome.attempt_count, 2)
        self.assertEqual(len(agent.repair_calls), 1)

    def test_carries_tool_calls_through_to_attempt_records(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result(
                "SELECT id FROM users",
                tool_calls=[{"name": "find_relevant_tables", "args": {}, "result": None}],
            ),
            repair_results=[
                make_generation_result(
                    "SELECT id FROM users LIMIT 10",
                    tool_calls=[{"name": "get_columns", "args": {}, "result": None}],
                ),
            ],
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertEqual(
            outcome.attempts[0].tool_calls,
            [{"name": "find_relevant_tables", "args": {}, "result": None}],
        )
        self.assertEqual(
            outcome.attempts[1].tool_calls,
            [{"name": "get_columns", "args": {}, "result": None}],
        )

    def test_records_non_negative_latency_per_attempt(self):
        agent = FakeQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users LIMIT 10")
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        outcome = loop.run(question="List users", metadata_json=METADATA)

        self.assertIsInstance(outcome.attempts[0].latency_ms, int)
        self.assertGreaterEqual(outcome.attempts[0].latency_ms, 0)

    def test_recursion_limit_exceeded_on_first_attempt_is_reraised_with_no_prior_attempts(self):
        agent = RaisingQueryAgent(generate_sql_error=AgentRecursionLimitExceeded())
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        with self.assertRaises(AgentRecursionLimitExceeded) as ctx:
            loop.run(question="List users", metadata_json=METADATA)

        self.assertEqual(ctx.exception.attempts_so_far, [])

    def test_timeout_during_repair_is_reraised_with_prior_attempts(self):
        agent = RaisingQueryAgent(
            generate_sql_result=make_generation_result("SELECT id FROM users"),
            repair_results=[SQLGenerationTimedOut()],
        )
        loop = QueryRepairLoop(query_agent=agent, after_guardrail=self.after_guardrail)

        with self.assertRaises(SQLGenerationTimedOut) as ctx:
            loop.run(question="List users", metadata_json=METADATA)

        self.assertEqual(len(ctx.exception.attempts_so_far), 1)
        self.assertEqual(ctx.exception.attempts_so_far[0].sql_query, "SELECT id FROM users")


if __name__ == "__main__":
    unittest.main()
