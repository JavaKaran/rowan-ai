import unittest
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app.exceptions import SQLGenerationFailed
from app.services.query_agent import (
    GeneratedSQL,
    LangChainQueryAgent,
    build_schema_retrieval_tools,
)
from app.services.schema_retrieval import SchemaRetrievalService

SAMPLE_METADATA = {
    "database_type": "postgresql",
    "database_name": "app_db",
    "schemas": [
        {
            "name": "public",
            "tables": [
                {
                    "name": "users",
                    "primary_key": ["id"],
                    "columns": [{"name": "id", "type": "INTEGER"}],
                    "foreign_keys": [],
                },
                {
                    "name": "orders",
                    "primary_key": ["id"],
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "user_id", "type": "INTEGER"},
                    ],
                    "foreign_keys": [
                        {
                            "columns": ["user_id"],
                            "referred_schema": "public",
                            "referred_table": "users",
                            "referred_columns": ["id"],
                        }
                    ],
                },
            ],
        }
    ],
    "relationships": [
        {
            "from_schema": "public",
            "from_table": "orders",
            "from_columns": ["user_id"],
            "to_schema": "public",
            "to_table": "users",
            "to_columns": ["id"],
        }
    ],
}


class BuildSchemaRetrievalToolsTest(unittest.TestCase):
    def test_tools_delegate_to_retrieval_service(self):
        service = SchemaRetrievalService(SAMPLE_METADATA)
        tools = build_schema_retrieval_tools(service)
        tool_by_name = {tool.name: tool for tool in tools}

        find_result = tool_by_name["find_relevant_tables"].invoke({"question": "show users"})
        columns_result = tool_by_name["get_columns"].invoke({"table_names": ["users"]})
        relationships_result = tool_by_name["get_relationships"].invoke(
            {"table_names": ["orders", "users"]}
        )

        self.assertEqual(find_result[0]["table"], "users")
        self.assertEqual(columns_result[0]["table"], "users")
        self.assertEqual(relationships_result[0]["from_table"], "orders")


class FakeAgent:
    def __init__(self, state):
        self.state = state
        self.invoked_with = None

    def invoke(self, input_):
        self.invoked_with = input_
        return self.state


class LangChainQueryAgentTest(unittest.TestCase):
    def test_generate_sql_returns_structured_result_with_usage_and_tool_calls(self):
        tool_message = AIMessage(
            content="",
            tool_calls=[
                {"name": "find_relevant_tables", "args": {"question": "show users"}, "id": "1"}
            ],
            usage_metadata={
                "total_tokens": 50,
                "input_tokens": 40,
                "output_tokens": 10,
                "input_token_details": {"cache_read": 5},
            },
        )
        final_message = AIMessage(
            content="done",
            usage_metadata={
                "total_tokens": 30,
                "input_tokens": 20,
                "output_tokens": 10,
                "input_token_details": {},
            },
        )
        state = {
            "messages": [tool_message, final_message],
            "structured_response": GeneratedSQL(
                sql_query="SELECT id FROM users LIMIT 10",
                summary="Lists user ids.",
            ),
        }
        captured = {}

        def agent_factory(llm, tools, system_prompt, response_format):
            captured["tools"] = sorted(tool.name for tool in tools)
            captured["system_prompt"] = system_prompt
            return FakeAgent(state)

        agent = LangChainQueryAgent(
            model_name="llama-3.3-70b-versatile",
            llm_factory=lambda model_name, temperature: None,
            agent_factory=agent_factory,
        )

        result = agent.generate_sql(question="Show users", metadata_json=SAMPLE_METADATA)

        self.assertEqual(result.sql_query, "SELECT id FROM users LIMIT 10")
        self.assertEqual(result.summary, "Lists user ids.")
        self.assertEqual(result.token_usage.total_tokens, 80)
        self.assertEqual(result.token_usage.input_tokens, 60)
        self.assertEqual(result.token_usage.output_tokens, 20)
        self.assertEqual(result.token_usage.cached_input_tokens, 5)
        self.assertEqual(result.provider, "groq")
        self.assertEqual(result.model_name, "llama-3.3-70b-versatile")
        self.assertEqual(
            result.tool_calls,
            [{"name": "find_relevant_tables", "args": {"question": "show users"}}],
        )
        self.assertEqual(
            captured["tools"],
            ["find_relevant_tables", "get_columns", "get_relationships"],
        )

    def test_generate_sql_aggregates_multiple_tool_call_rounds(self):
        round_one = AIMessage(
            content="",
            tool_calls=[
                {"name": "find_relevant_tables", "args": {"question": "show users"}, "id": "1"},
                {"name": "get_columns", "args": {"table_names": ["users"]}, "id": "2"},
            ],
            usage_metadata={
                "total_tokens": 40,
                "input_tokens": 30,
                "output_tokens": 10,
                "input_token_details": {},
            },
        )
        round_two = AIMessage(
            content="",
            tool_calls=[
                {"name": "get_relationships", "args": {"table_names": ["users", "orders"]}, "id": "3"},
            ],
            usage_metadata={
                "total_tokens": 25,
                "input_tokens": 15,
                "output_tokens": 10,
                "input_token_details": {},
            },
        )
        final_message = AIMessage(
            content="done",
            usage_metadata={
                "total_tokens": 20,
                "input_tokens": 10,
                "output_tokens": 10,
                "input_token_details": {},
            },
        )
        state = {
            "messages": [round_one, round_two, final_message],
            "structured_response": GeneratedSQL(
                sql_query="SELECT users.id FROM users JOIN orders ON orders.user_id = users.id LIMIT 10",
                summary="Joins users and orders.",
            ),
        }
        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=lambda *args, **kwargs: FakeAgent(state),
        )

        result = agent.generate_sql(question="Join users and orders", metadata_json=SAMPLE_METADATA)

        self.assertEqual(
            result.tool_calls,
            [
                {"name": "find_relevant_tables", "args": {"question": "show users"}},
                {"name": "get_columns", "args": {"table_names": ["users"]}},
                {"name": "get_relationships", "args": {"table_names": ["users", "orders"]}},
            ],
        )
        self.assertEqual(result.token_usage.total_tokens, 85)
        self.assertEqual(result.token_usage.input_tokens, 55)
        self.assertEqual(result.token_usage.output_tokens, 30)

    def test_generate_sql_excludes_synthetic_structured_output_tool_call(self):
        real_tool_call = AIMessage(
            content="",
            tool_calls=[{"name": "find_relevant_tables", "args": {"question": "show users"}, "id": "1"}],
        )
        structured_output_submission = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "GeneratedSQL",
                    "args": {"sql_query": "SELECT id FROM users LIMIT 10", "summary": "ok"},
                    "id": "2",
                }
            ],
        )
        state = {
            "messages": [real_tool_call, structured_output_submission],
            "structured_response": GeneratedSQL(
                sql_query="SELECT id FROM users LIMIT 10", summary="ok"
            ),
        }
        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=lambda *args, **kwargs: FakeAgent(state),
        )

        result = agent.generate_sql(question="Show users", metadata_json=SAMPLE_METADATA)

        self.assertEqual(
            result.tool_calls,
            [{"name": "find_relevant_tables", "args": {"question": "show users"}}],
        )

    def test_generate_sql_includes_session_context_in_user_message(self):
        state = {
            "messages": [],
            "structured_response": GeneratedSQL(sql_query="SELECT 1", summary="ok"),
        }
        captured = {}

        def agent_factory(llm, tools, system_prompt, response_format):
            def invoke(input_):
                captured["input"] = input_
                return state

            return SimpleNamespace(invoke=invoke)

        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=agent_factory,
        )

        agent.generate_sql(
            question="Now only enterprise",
            metadata_json=SAMPLE_METADATA,
            last_user_question="Show orders by month",
            last_sql_query="SELECT 1 FROM orders",
        )

        user_message = captured["input"]["messages"][0][1]
        self.assertIn("last_user_question: Show orders by month", user_message)
        self.assertIn("last_sql_query: SELECT 1 FROM orders", user_message)
        self.assertIn("Current user question:\nNow only enterprise", user_message)

    def test_generate_sql_raises_when_structured_response_missing(self):
        state = {"messages": [], "structured_response": None}
        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=lambda *args, **kwargs: FakeAgent(state),
        )

        with self.assertRaises(SQLGenerationFailed):
            agent.generate_sql(question="x", metadata_json=SAMPLE_METADATA)

    def test_generate_sql_raises_when_agent_invocation_fails(self):
        class FailingAgent:
            def invoke(self, input_):
                raise RuntimeError("network down")

        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=lambda *args, **kwargs: FailingAgent(),
        )

        with self.assertRaises(SQLGenerationFailed):
            agent.generate_sql(question="x", metadata_json=SAMPLE_METADATA)

    def test_repair_sql_includes_previous_sql_and_failure_detail_in_message(self):
        state = {
            "messages": [],
            "structured_response": GeneratedSQL(
                sql_query="SELECT id FROM users LIMIT 10", summary="fixed"
            ),
        }
        captured = {}

        def agent_factory(llm, tools, system_prompt, response_format):
            def invoke(input_):
                captured["input"] = input_
                return state

            return SimpleNamespace(invoke=invoke)

        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=agent_factory,
        )

        result = agent.repair_sql(
            question="Show users",
            metadata_json=SAMPLE_METADATA,
            previous_sql="SELECT id FROM users",
            failure_category="missing_limit",
            failure_detail="Queries must include a LIMIT unless they are aggregate-only reads.",
        )

        self.assertEqual(result.sql_query, "SELECT id FROM users LIMIT 10")
        user_message = captured["input"]["messages"][0][1]
        self.assertIn("SELECT id FROM users", user_message)
        self.assertIn("missing_limit", user_message)
        self.assertIn(
            "Queries must include a LIMIT unless they are aggregate-only reads.",
            user_message,
        )
        self.assertIn("Show users", user_message)

    def test_repair_sql_includes_session_context_like_generate_sql(self):
        state = {
            "messages": [],
            "structured_response": GeneratedSQL(sql_query="SELECT 1", summary="ok"),
        }
        captured = {}

        def agent_factory(llm, tools, system_prompt, response_format):
            def invoke(input_):
                captured["input"] = input_
                return state

            return SimpleNamespace(invoke=invoke)

        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=agent_factory,
        )

        agent.repair_sql(
            question="Now only enterprise",
            metadata_json=SAMPLE_METADATA,
            previous_sql="SELECT 1",
            failure_category="missing_limit",
            failure_detail="needs a limit",
            last_user_question="Show orders by month",
            last_sql_query="SELECT 1 FROM orders",
        )

        user_message = captured["input"]["messages"][0][1]
        self.assertIn("last_user_question: Show orders by month", user_message)
        self.assertIn("last_sql_query: SELECT 1 FROM orders", user_message)

    def test_repair_sql_raises_when_agent_invocation_fails(self):
        class FailingAgent:
            def invoke(self, input_):
                raise RuntimeError("network down")

        agent = LangChainQueryAgent(
            model_name="m",
            llm_factory=lambda *args: None,
            agent_factory=lambda *args, **kwargs: FailingAgent(),
        )

        with self.assertRaises(SQLGenerationFailed):
            agent.repair_sql(
                question="x",
                metadata_json=SAMPLE_METADATA,
                previous_sql="SELECT 1",
                failure_category="missing_limit",
                failure_detail="needs a limit",
            )


if __name__ == "__main__":
    unittest.main()
