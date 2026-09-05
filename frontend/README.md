# Rowan frontend

Next.js App Router, TypeScript, Tailwind CSS v4, TanStack Query and Radix Tabs.

## Run

```sh
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. Run the existing FastAPI backend separately, with its database migrations and environment configured. `BACKEND_URL` defaults to `http://127.0.0.1:8000`; set it in `.env.local` when the backend is elsewhere. The Next.js API proxy keeps browser requests same-origin, so backend CORS changes are unnecessary. For remote deployment, use HTTPS.

```sh
npm run typecheck
npm run lint
npm run build
```

## Flow and API contract

- `/` is the landing page. Its illustrative conversation is explicitly labeled as an example.
- `/workspace` creates an unnamed workspace with `POST /workspace/` and `{ "name": "" }` (the current database column disallows null), saves `workspace_key` as `rowan.workspace` in localStorage, and validates it with `GET /workspace/{key}` on reopening. Only a 404 replaces an old workspace.
- New conversations call `POST /session/` with `X-Workspace-Key` and an empty body. Session references and successful connection labels are saved under `rowan.sessions.{workspace_key}`.
- Connection setup calls `POST /connection/` with both workspace and session headers. Supported types match the current API: PostgreSQL and MySQL. A new database requires a new conversation.
- Questions call `POST /query/`. Results expose rows, SQL, optional summary, truncation, execution duration, tokens, repair count and tool traces. Large results paginate in groups of 20. CSV export escapes quotes and spreadsheet formula prefixes.
- Credentials and query results are never persisted in browser storage. Browser storage contains workspace/session keys, conversation labels and database labels. Treat the workspace key as access-bearing; the backend currently provides no user authentication.
- The current backend has no history listing, connection status, metadata status or streaming endpoints. Connection badges reflect the last successful connection; query failures report current backend errors. Reloading clears displayed results while retaining the session. Metadata-not-ready errors offer manual retry without automatically replaying queries.

## Structure

`src/lib/api.ts` owns typed requests and workspace initialization. `src/components/connection-form.tsx` handles connection setup, `query-result.tsx` renders answers, and `providers.tsx` supplies React Query. The workspace route owns session and conversation state. `src/app/api/[...path]/route.ts` proxies an allowlisted set of backend routes. `globals.css` defines a compact shared visual system and responsive layouts.
