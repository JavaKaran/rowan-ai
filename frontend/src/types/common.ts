/** Shared request context sent as `X-Workspace-Key` / `X-Session-Key` headers. */
export type Context = { workspace: string; session?: string };
