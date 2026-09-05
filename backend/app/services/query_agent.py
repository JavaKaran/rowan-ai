import json
import os
from typing import Any, Callable

import groq
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.errors import GraphRecursionError
from pydantic import BaseModel

from app.exceptions import AgentRecursionLimitExceeded, SQLGenerationFailed, SQLGenerationTimedOut
from app.schemas import QueryTokenUsage
from app.services.schema_retrieval import SchemaRetrievalService

DEFAULT_RECURSION_LIMIT = 20
DEFAULT_LLM_TIMEOUT_SECONDS = 60.0

AGENT_SYSTEM_PROMPT = (
    "You are a read-only SQL generation assistant. "
    "You do not have the database schema in advance. "
    "Call find_relevant_tables to discover candidate tables for the question, "
    "call get_columns on the tables you actually plan to use, and call "
    "get_relationships when a join is needed. Only use tables and columns "
    "returned by these tools. Never guess schema. "
    "Use the SQL dialect indicated by target_database_type exactly. "
    "For meta-questions about the database itself (e.g. what tables exist, "
    "what columns a table has), query the standard information_schema views "
    "(information_schema.tables, information_schema.columns) instead of the "
    "application tables. Generate exactly one "
    "read-only SQL query and a short summary that explains what the query "
    "does. Add a LIMIT when the question does not require the full dataset."
)


class GeneratedSQL(BaseModel):
    sql_query: str
    summary: str


class QueryAgentResult(BaseModel):
    sql_query: str
    summary: str
    token_usage: QueryTokenUsage
    provider: str
    model_name: str
    tool_calls: list[dict[str, Any]]


def build_schema_retrieval_tools(retrieval_service: SchemaRetrievalService) -> list[Any]:
    @tool
    def find_relevant_tables(question: str) -> list[dict[str, Any]]:
        """Find tables likely relevant to a natural language question."""
        return retrieval_service.find_relevant_tables(question)

    @tool
    def get_columns(table_names: list[str]) -> list[dict[str, Any]]:
        """Get columns and primary key for the given table names."""
        return retrieval_service.get_columns(table_names)

    @tool
    def get_relationships(table_names: list[str]) -> list[dict[str, Any]]:
        """Get foreign key relationships touching the given table names."""
        return retrieval_service.get_relationships(table_names)

    return [find_relevant_tables, get_columns, get_relationships]


class LangChainQueryAgent:
    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        provider: str = "groq",
        recursion_limit: int = DEFAULT_RECURSION_LIMIT,
        timeout_seconds: float = DEFAULT_LLM_TIMEOUT_SECONDS,
        llm_factory: Callable[[str, float, float], Any] | None = None,
        agent_factory: Callable[..., Any] | None = None,
    ):
        self.model_name = model_name
        self.temperature = temperature
        self.provider = provider
        self.recursion_limit = recursion_limit
        self.timeout_seconds = timeout_seconds
        self._llm_factory = llm_factory or self._default_llm_factory
        self._agent_factory = agent_factory or create_agent

    @staticmethod
    def _default_llm_factory(model_name: str, temperature: float, timeout_seconds: float) -> Any:
        return ChatGroq(model_name=model_name, temperature=temperature, timeout=timeout_seconds)

    def generate_sql(
        self,
        question: str,
        metadata_json: dict[str, Any],
        last_user_question: str | None = None,
        last_sql_query: str | None = None,
    ) -> QueryAgentResult:
        user_message = self._build_user_message(
            question,
            metadata_json,
            last_user_question,
            last_sql_query,
        )
        return self._run(metadata_json, user_message)

    def repair_sql(
        self,
        question: str,
        metadata_json: dict[str, Any],
        previous_sql: str,
        failure_category: str,
        failure_detail: str,
        last_user_question: str | None = None,
        last_sql_query: str | None = None,
    ) -> QueryAgentResult:
        user_message = self._build_repair_message(
            question,
            metadata_json,
            previous_sql,
            failure_category,
            failure_detail,
            last_user_question,
            last_sql_query,
        )
        return self._run(metadata_json, user_message)

    def _run(self, metadata_json: dict[str, Any], user_message: str) -> QueryAgentResult:
        retrieval_service = SchemaRetrievalService(metadata_json)
        tools = build_schema_retrieval_tools(retrieval_service)
        llm = self._llm_factory(self.model_name, self.temperature, self.timeout_seconds)
        agent = self._agent_factory(
            llm,
            tools=tools,
            system_prompt=AGENT_SYSTEM_PROMPT,
            # Force ToolStrategy: AutoStrategy would pick provider-native JSON
            # mode for models whose profile claims structured_output support,
            # but Groq's API rejects JSON mode combined with tool calling.
            response_format=ToolStrategy(GeneratedSQL),
        )

        try:
            state = agent.invoke(
                {"messages": [("user", user_message)]},
                config={"recursion_limit": self.recursion_limit},
            )
        except GraphRecursionError as exc:
            raise AgentRecursionLimitExceeded() from exc
        except groq.APITimeoutError as exc:
            raise SQLGenerationTimedOut() from exc
        except Exception as exc:
            raise SQLGenerationFailed("Failed to generate SQL query.") from exc

        structured = state.get("structured_response")
        if structured is None:
            raise SQLGenerationFailed("Model response could not be parsed.")

        sql_query = structured.sql_query.strip()
        if not sql_query:
            raise SQLGenerationFailed("Model returned an empty SQL query.")

        summary = structured.summary.strip()
        if not summary:
            raise SQLGenerationFailed("Model returned an empty query summary.")

        messages = state.get("messages", [])
        return QueryAgentResult(
            sql_query=sql_query,
            summary=summary,
            token_usage=self._aggregate_token_usage(messages),
            provider=self.provider,
            model_name=self.model_name,
            tool_calls=self._extract_tool_calls(messages),
        )

    def _build_repair_message(
        self,
        question: str,
        metadata_json: dict[str, Any],
        previous_sql: str,
        failure_category: str,
        failure_detail: str,
        last_user_question: str | None,
        last_sql_query: str | None,
    ) -> str:
        lines = []
        if last_user_question:
            lines.append(f"last_user_question: {last_user_question}")
        if last_sql_query:
            lines.append(f"last_sql_query: {last_sql_query}")
        if lines:
            lines.append("")
        lines.extend(self._database_context_lines(metadata_json))
        lines.append("")
        lines.append(f"Current user question:\n{question.strip()}")
        lines.append("")
        lines.append(
            "The previous SQL candidate was rejected by the safety guardrail. "
            "Make the smallest possible change to fix the reported issue — do "
            "not rewrite the query from scratch unless required."
        )
        lines.append(f"previous_sql: {previous_sql}")
        lines.append(f"guardrail_failure_category: {failure_category}")
        lines.append(f"guardrail_failure_detail: {failure_detail}")
        return "\n".join(lines)

    def _build_user_message(
        self,
        question: str,
        metadata_json: dict[str, Any],
        last_user_question: str | None,
        last_sql_query: str | None,
    ) -> str:
        lines = []
        if last_user_question:
            lines.append(f"last_user_question: {last_user_question}")
        if last_sql_query:
            lines.append(f"last_sql_query: {last_sql_query}")
        if lines:
            lines.append("")
        lines.extend(self._database_context_lines(metadata_json))
        lines.append("")
        lines.append(f"Current user question:\n{question.strip()}")
        return "\n".join(lines)

    def _database_context_lines(self, metadata_json: dict[str, Any]) -> list[str]:
        database_type = metadata_json.get("database_type", "unknown")
        database_name = metadata_json.get("database_name", "unknown")
        return [
            f"target_database_type: {database_type}",
            f"target_database_name: {database_name}",
            "Generate SQL using exactly the target_database_type dialect.",
        ]

    def _aggregate_token_usage(self, messages: list[Any]) -> QueryTokenUsage:
        total_tokens = input_tokens = output_tokens = cached_input_tokens = 0
        for message in messages:
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                continue
            total_tokens += usage.get("total_tokens", 0)
            input_tokens += usage.get("input_tokens", 0)
            output_tokens += usage.get("output_tokens", 0)
            input_details = usage.get("input_token_details", {}) or {}
            cached_input_tokens += input_details.get("cache_read", 0) or 0

        return QueryTokenUsage(
            total_tokens=total_tokens,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
        )

    def _extract_tool_calls(self, messages: list[Any]) -> list[dict[str, Any]]:
        results_by_call_id = {
            message.tool_call_id: self._parse_tool_result(message.content)
            for message in messages
            if isinstance(message, ToolMessage)
        }

        tool_calls: list[dict[str, Any]] = []
        for message in messages:
            for call in getattr(message, "tool_calls", None) or []:
                if call.get("name") == GeneratedSQL.__name__:
                    continue
                tool_calls.append(
                    {
                        "name": call.get("name"),
                        "args": call.get("args"),
                        "result": results_by_call_id.get(call.get("id")),
                    }
                )
        return tool_calls

    def _parse_tool_result(self, content: Any) -> Any:
        if not isinstance(content, str):
            return content
        try:
            return json.loads(content)
        except (TypeError, ValueError):
            return content


def create_query_agent() -> LangChainQueryAgent:
    provider = os.getenv("QUERY_MODEL_PROVIDER", "groq").lower()
    model_name = os.getenv("QUERY_MODEL_NAME", "qwen/qwen3.8-27b")
    recursion_limit = int(os.getenv("AGENT_RECURSION_LIMIT", str(DEFAULT_RECURSION_LIMIT)))

    if provider == "groq":
        return LangChainQueryAgent(
            model_name=model_name,
            temperature=0.0,
            provider=provider,
            recursion_limit=recursion_limit,
        )

    raise ValueError(f"Unsupported QUERY_MODEL_PROVIDER: {provider}")
