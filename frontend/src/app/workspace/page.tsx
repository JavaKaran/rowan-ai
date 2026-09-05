"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUp,
  Plus,
  MessageSquare,
  LoaderCircle,
  PanelLeftClose,
  PanelLeftOpen,
  RotateCcw,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ConnectionForm } from "@/components/connection-form";
import { QueryResult } from "@/components/query-result";
import {
  ApiError,
  ensureWorkspace,
  QueryResult as Result,
  request,
  SessionDetail,
} from "@/lib/api";
type Session = { key: string; name: string; database?: string; type?: string };
type Turn = { id: string; question: string; result?: Result; error?: string };
export default function Workspace() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ sessionId?: string }>();
  const initialSessionKey =
    typeof params.sessionId === "string" ? params.sessionId : undefined;
  const isSessionRoute = pathname.startsWith("/workspace/session/");
  const workspace = useQuery({
    queryKey: ["workspace"],
    queryFn: ensureWorkspace,
    staleTime: Infinity,
  });
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<string>();
  const [loaded, setLoaded] = useState(false);
  const [storageError, setStorageError] = useState("");
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Record<string, Turn[]>>({});
  const [collapsed, setCollapsed] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const hydratedHistoryRef = useRef<Set<string>>(new Set());
  const session = sessions.find((item) => item.key === active);
  useEffect(() => {
    if (!workspace.data) return;
    try {
      const saved = JSON.parse(
        localStorage.getItem(`rowan.sessions.${workspace.data}`) || "[]",
      );
      if (Array.isArray(saved)) {
        const valid = saved.filter(
          (s) => s && typeof s.key === "string" && typeof s.name === "string",
        );
        setSessions(valid);
        setActive(
          initialSessionKey && valid.some((item) => item.key === initialSessionKey)
            ? initialSessionKey
            : undefined,
        );
      }
    } catch {
      setStorageError(
        "Browser storage could not be read. Your sessions may not be available after reloading.",
      );
    }
    setLoaded(true);
  }, [initialSessionKey, workspace.data]);
  useEffect(() => {
    if (!loaded || !initialSessionKey) {
      setActive(undefined);
      return;
    }
    if (sessions.some((item) => item.key === initialSessionKey)) {
      setActive(initialSessionKey);
    }
  }, [initialSessionKey, loaded, sessions]);
  const sessionLookup = useQuery({
    queryKey: ["session", workspace.data, initialSessionKey],
    queryFn: () =>
      request<SessionDetail>(
        `session/${encodeURIComponent(initialSessionKey!)}`,
        { workspace: workspace.data! },
      ),
    enabled: Boolean(workspace.data) && loaded && Boolean(initialSessionKey),
    retry: false,
  });
  useEffect(() => {
    const data = sessionLookup.data;
    if (!data) return;
    const hydrated = {
      key: data.session_key,
      name: data.name || "New conversation",
    };
    setSessions((items) =>
      items.some((item) => item.key === hydrated.key)
        ? items
        : [hydrated, ...items],
    );
    setActive(hydrated.key);
  }, [sessionLookup.data]);
  useEffect(() => {
    const data = sessionLookup.data;
    if (!data) return;
    if (hydratedHistoryRef.current.has(data.session_key)) return;
    hydratedHistoryRef.current.add(data.session_key);
    if (!data.messages.length) return;
    setTurns((previous) =>
      previous[data.session_key]
        ? previous
        : {
            ...previous,
            [data.session_key]: data.messages.map((message) => ({
              id: crypto.randomUUID(),
              question: message.question,
              result: message.status === "completed" ? message : undefined,
              error:
                message.status === "completed"
                  ? undefined
                  : message.error_message ||
                    "This question could not be completed.",
            })),
          },
    );
  }, [sessionLookup.data]);
  useEffect(() => {
    if (loaded && workspace.data) {
      try {
        localStorage.setItem(
          `rowan.sessions.${workspace.data}`,
          JSON.stringify(sessions),
        );
      } catch {
        setStorageError(
          "Browser storage is full or unavailable. This session will not be saved after reloading.",
        );
      }
    }
  }, [sessions, loaded, workspace.data]);
  const newSession = useMutation({
    mutationFn: () =>
      request<{ session_key: string }>(
        "session/",
        { workspace: workspace.data! },
        {},
      ),
    onSuccess: (data) => {
      const next = { key: data.session_key, name: "New conversation" };
      setSessions((items) => [next, ...items]);
      setActive(next.key);
      setQuestion("");
      router.push(`/workspace/session/${encodeURIComponent(next.key)}`);
    },
  });
  const query = useMutation({
    mutationFn: ({ text, key }: { text: string; key: string; id: string }) =>
      request<Result>(
        "query/",
        { workspace: workspace.data!, session: key },
        { question: text },
      ),
    onSuccess: (result, variables) =>
      setTurns((previous) => ({
        ...previous,
        [variables.key]: (previous[variables.key] || []).map((turn) =>
          turn.id === variables.id ? { ...turn, result } : turn,
        ),
      })),
    onError: (error, variables) => {
      let message = error.message;
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        message.includes("metadata")
      )
        message =
          "Your database schema is still being prepared. Wait a moment, then retry your question.";
      setTurns((previous) => ({
        ...previous,
        [variables.key]: (previous[variables.key] || []).map((turn) =>
          turn.id === variables.id ? { ...turn, error: message } : turn,
        ),
      }));
    },
  });
  const currentTurns = active ? turns[active] || [] : [];
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentTurns.length, query.isPending]);
  function ask(text: string) {
    if (!active || !session?.database || !text.trim() || query.isPending)
      return;
    const id = crypto.randomUUID();
    setTurns((previous) => ({
      ...previous,
      [active]: [...(previous[active] || []), { id, question: text.trim() }],
    }));
    setSessions((items) =>
      items.map((item) =>
        item.key === active && item.name === "New conversation"
          ? { ...item, name: text.trim().slice(0, 46) }
          : item,
      ),
    );
    setQuestion("");
    query.mutate({ text: text.trim(), key: active, id });
  }
  return (
    <div className={`workspace ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-heading">
          <Brand />
          <button
            className="icon-button"
            aria-label="Collapse sidebar"
            onClick={() => setCollapsed(true)}
          >
            <PanelLeftClose size={18} />
          </button>
        </div>
        <button
          className="button new-session"
          onClick={() => newSession.mutate()}
          disabled={
            !workspace.data ||
            !loaded ||
            newSession.isPending ||
            query.isPending
          }
        >
          <Plus size={17} />
          New conversation
        </button>
        <div className="sidebar-label">Your conversations</div>
        <div className="session-list">
          {sessions.map((item) => (
            <button
              key={item.key}
              className={active === item.key ? "active" : ""}
              onClick={() => {
                setActive(item.key);
                setQuestion("");
                router.push(`/workspace/session/${encodeURIComponent(item.key)}`);
              }}
            >
              <MessageSquare size={16} />
              <span>
                {item.name}
                <small>{item.database || "Connect a database"}</small>
              </span>
            </button>
          ))}
        </div>
      </aside>
      <main className="workspace-main">
        <header className="workspace-header">
          <div>
            {collapsed && (
              <>
                <Brand />
                <button
                  className="icon-button"
                  aria-label="Expand sidebar"
                  onClick={() => setCollapsed(false)}
                >
                  <PanelLeftOpen size={19} />
                </button>
              </>
            )}
            <strong className="header-db">{session?.database || "Get started"}</strong>
            <span className="badge">
              <span
                className={
                  session?.database ? "status-dot" : "status-dot neutral"
                }
              />
              {session?.database ? "Connected" : "No database connected"}
            </span>
          </div>
        </header>
        {storageError && (
          <div className="error" role="alert">
            {storageError}
          </div>
        )}
        {newSession.error && (
          <div className="error" role="alert">
            {newSession.error.message}
          </div>
        )}
        {workspace.isPending ? (
          <div className="center-state">
            <LoaderCircle className="spin" />
            Preparing your workspace…
          </div>
        ) : workspace.error ? (
          <div className="center-state">
            <h1>Couldn’t open your workspace</h1>
            <p role="alert">{workspace.error.message}</p>
            <button className="button" onClick={() => workspace.refetch()}>
              Try again
            </button>
          </div>
        ) : !session ? (
          <div className="center-state">
            <div className="large-icon">
              <MessageSquare size={27} />
            </div>
            {isSessionRoute && sessionLookup.isPending ? (
              <>
                <h1>Opening conversation.</h1>
                <p>Loading this session for your workspace.</p>
              </>
            ) : isSessionRoute && sessionLookup.error ? (
              <>
                <h1>Conversation not found.</h1>
                <p role="alert">
                  This session is unavailable for the current workspace.
                </p>
              </>
            ) : (
              <>
                <h1>No conversation selected.</h1>
                <p>Select a conversation from the sidebar or start a new one.</p>
                <button
                  className="button"
                  disabled={!loaded || newSession.isPending}
                  onClick={() => newSession.mutate()}
                >
                  {newSession.isPending ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <Plus size={16} />
                  )}
                  Start a conversation
                </button>
              </>
            )}
          </div>
        ) : !session.database ? (
          <div className="connection-container">
            <ConnectionForm
              key={session.key}
              context={{ workspace: workspace.data!, session: session.key }}
              onConnected={(database, type) =>
                setSessions((items) =>
                  items.map((item) =>
                    item.key === session.key
                      ? { ...item, database, type }
                      : item,
                  ),
                )
              }
            />
          </div>
        ) : (
          <>
            <div className="conversation">
              <div className="conversation-inner">
                {!currentTurns.length ? (
                  <div className="chat-welcome">
                    <h1>What would you like to know?</h1>
                    <p>
                      Ask about your data in your own words.
                      <br />
                      We’ll bring back the results and the SQL behind them.
                    </p>
                    <div className="suggestions">
                      {[
                        "How many records are in my data?",
                        "Show me 10 sample rows to explore",
                        "Summarize the highlights in my data",
                      ].map((text) => (
                        <button key={text} onClick={() => setQuestion(text)}>
                          {text}
                          <ArrowUp size={15} />
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  currentTurns.map((turn) => (
                    <article className="turn" key={turn.id}>
                      <div className="user-question">
                        <span>You</span>
                        <p>{turn.question}</p>
                      </div>
                      {turn.result ? (
                        <QueryResult result={turn.result} />
                      ) : turn.error ? (
                        <div className="error" role="alert">
                          <p>{turn.error}</p>
                          <button
                            className="text-button retry-button"
                            disabled={query.isPending}
                            onClick={() => ask(turn.question)}
                          >
                            <RotateCcw size={14} />
                            Retry question
                          </button>
                        </div>
                      ) : (
                        <div className="thinking" role="status">
                          <LoaderCircle size={17} className="spin" />
                          Working on your question. This may take a moment.
                        </div>
                      )}
                    </article>
                  ))
                )}
                <div ref={bottom} />
              </div>
            </div>
            <div className="composer-wrap">
              <form
                className="composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  ask(question);
                }}
              >
                <div className="composer-row">
                  <textarea
                    aria-label="Ask a question about your data"
                    placeholder="Ask anything about your data…"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => {
                      if (
                        event.key === "Enter" &&
                        !event.shiftKey &&
                        !event.nativeEvent.isComposing
                      ) {
                        event.preventDefault();
                        ask(question);
                      }
                    }}
                    rows={2}
                    maxLength={10000}
                  />
                  <button
                    className="send-button"
                    type="submit"
                    aria-label="Send question"
                    disabled={!question.trim() || query.isPending}
                  >
                    {query.isPending ? (
                      <LoaderCircle size={18} className="spin" />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </form>
              <p>Rowan can make mistakes. Check important info.</p>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
