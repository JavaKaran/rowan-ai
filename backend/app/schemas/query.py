from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryTokenUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


class QueryToolCallInfo(BaseModel):
    attempt_number: int
    name: str | None
    args: dict[str, Any] | None
    result: Any | None = None


class QueryResponse(BaseModel):
    sql_query: str
    summary: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: int
    truncated: bool
    token_usage: QueryTokenUsage
    attempt_count: int = 1
    repaired: bool = False
    tool_calls: list[QueryToolCallInfo] = Field(default_factory=list)
