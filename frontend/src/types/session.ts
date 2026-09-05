import type { QueryResult } from "./query";

/**
 * Session types.
 * Mirrors `backend/app/schemas/session.py`
 * (`SessionQueryHistoryItem` / `SessionResponse` /
 * `SessionListItem` / `SessionListResponse`)
 * backed by the `sessions` table plus the first user `messages` row.
 */
export type SessionMessage = QueryResult & {
  question: string;
  status: string;
  error_message?: string | null;
};

export type SessionDetail = {
  session_key: string;
  name: string | null;
  is_connected: boolean;
  messages: SessionMessage[];
};

export type SessionListItem = {
  session_key: string;
  name: string | null;
  first_message: string | null;
  is_connected: boolean;
};

export type SessionListResponse = {
  items: SessionListItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

/**
 * Workspace session as used by the UI: the backend list item plus
 * local-only connection display details. `is_connected` is authoritative
 * from the backend and survives reloads; `database` / `type` (the exact
 * connection name/dialect) are only known locally after connecting in the
 * current page lifetime, since the backend doesn't echo them back.
 */
export type Session = SessionListItem & {
  database?: string;
  type?: string;
};

/** Local chat turn state for a session (not persisted by the backend). */
export type Turn = {
  id: string;
  question: string;
  result?: QueryResult;
  error?: string;
};
