from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    system_prompt: str | None = Field(default=None)


class QueryTokenUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int


class QueryResponse(BaseModel):
    sql_query: str
    summary: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_time_ms: int
    truncated: bool
    token_usage: QueryTokenUsage
