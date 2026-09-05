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
  messages: SessionMessage[];
};

export type SessionListItem = {
  session_key: string;
  name: string | null;
  first_message: string | null;
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
 * local-only connection state (the backend exposes no connection-status
 * endpoint, so `database` / `type` are only known after connecting
 * in the current page lifetime).
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
