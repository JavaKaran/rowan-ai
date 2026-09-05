/**
 * Query types.
 * Mirrors `backend/app/schemas/query.py`
 * (`QueryTokenUsage` / `QueryToolCallInfo` / `QueryResponse`)
 * backed by the `queries`, `query_attempts` and `tokens` tables.
 */
export type QueryTokenUsage = {
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
};

export type QueryToolCallInfo = {
  attempt_number: number;
  name: string | null;
  args: Record<string, unknown> | null;
  result?: unknown;
};

export type QueryResult = {
  sql_query: string;
  summary: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  execution_time_ms: number;
  truncated: boolean;
  token_usage: QueryTokenUsage;
  attempt_count: number;
  repaired: boolean;
  tool_calls: QueryToolCallInfo[];
};
