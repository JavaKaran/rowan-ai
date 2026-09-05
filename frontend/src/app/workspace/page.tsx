"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowUp,
  Database,
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
} from "@/lib/api";
type Session = { key: string; name: string; database?: string; type?: string };
type Turn = { id: string; question: string; result?: Result; error?: string };
export default function Workspace() {
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
        setActive(valid[0]?.key);
      }
    } catch {
      setStorageError(
        "Browser storage could not be read. Your sessions may not be available after reloading.",
      );
    }
    setLoaded(true);
  }, [workspace.data]);
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
            <h1>A fresh place to explore.</h1>
            <p>
              Start a conversation, connect your database, and follow your
              curiosity.
            </p>
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
                    <div className="large-icon">
                      <Database size={25} />
                    </div>
                    <span className="connected-label">
                      {session.database} is connected
                    </span>
                    <h1>What would you like to know?</h1>
                    <p>
                      Ask about your data in your own words.
                      <br />
                      We’ll bring back the results and the SQL behind them.
                    </p>
                    <div className="suggestions">
                      {[
                        "What tables can I explore?",
                        "Give me an overview of my data",
                        "What trends can you find?",
                      ].map((text) => (
                        <button key={text} onClick={() => setQuestion(text)}>
                          {text}
                          <ArrowUp size={15} />
                        </button>
                      ))}
                    </div>
                    <p className="small-note">
                      Earlier results aren’t restored after a reload. You can
                      keep asking questions in this session.
                    </p>
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
