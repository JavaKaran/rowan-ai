"use client";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
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
import { ApiError, ensureWorkspace, request } from "@/lib/api";
import type {
  QueryResult as Result,
  Session,
  SessionDetail,
  SessionListResponse,
  Turn,
} from "@/types";
function sessionDisplayName(item: Session): string {
  return (
    item.name || item.first_message?.slice(0, 46) || "New conversation"
  );
}
export default function WorkspaceLayout({
  children,
}: {
  children: ReactNode;
}) {
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
  const [question, setQuestion] = useState("");
  const [turns, setTurns] = useState<Record<string, Turn[]>>({});
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    if (window.matchMedia("(max-width: 540px)").matches) setCollapsed(true);
  }, []);
  const bottom = useRef<HTMLDivElement>(null);
  const hydratedHistoryRef = useRef<Set<string>>(new Set());
  const sessionListRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const sessionLookup = useQuery({
    queryKey: ["session", workspace.data, initialSessionKey],
    queryFn: () =>
      request<SessionDetail>(
        `session/${encodeURIComponent(initialSessionKey!)}`,
        { workspace: workspace.data! },
      ),
    enabled: Boolean(workspace.data) && Boolean(initialSessionKey),
    retry: false,
  });
  useEffect(() => {
    const data = sessionLookup.data;
    if (!data) return;
    const hydrated: Session = {
      session_key: data.session_key,
      name: data.name,
      first_message: data.messages[0]?.question ?? null,
      is_connected: data.metadata?.is_connected ?? data.is_connected,
      database: data.metadata?.database_name ?? undefined,
      type: data.metadata?.database_type ?? undefined,
    };
    setSessions((items) =>
      items.some((item) => item.session_key === hydrated.session_key)
        ? items
        : [hydrated, ...items],
    );
    setActive(hydrated.session_key);
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
  const sessionsQuery = useInfiniteQuery({
    queryKey: ["sessions", workspace.data],
    queryFn: ({ pageParam }) =>
      request<SessionListResponse>(`session/?page=${pageParam}`, {
        workspace: workspace.data!,
      }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) =>
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined,
    enabled: Boolean(workspace.data),
  });
  // Sidebar order always mirrors the API response (newest first). `sessions`
  // state only carries local extras (connection state, optimistic renames):
  // entries already returned by the API render in API order with those
  // extras overlaid, while optimistic entries not yet in the API stay on top
  // (where the API will also place them once persisted, newest first).
  const apiSessions = useMemo(
    () => sessionsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [sessionsQuery.data],
  );
  const visibleSessions: Session[] = useMemo(() => {
    const localByKey = new Map(sessions.map((item) => [item.session_key, item]));
    const apiKeys = new Set(apiSessions.map((item) => item.session_key));
    const pending = sessions.filter((item) => !apiKeys.has(item.session_key));
    return [
      ...pending,
      ...apiSessions.map((item) => {
        const local = localByKey.get(item.session_key);
        return {
          session_key: item.session_key,
          name: local?.name ?? item.name,
          first_message: local?.first_message ?? item.first_message,
          is_connected: local?.is_connected ?? item.is_connected,
          database: local?.database,
          type: local?.type,
        };
      }),
    ];
  }, [sessions, apiSessions]);
  const session = visibleSessions.find(
    (item) => item.session_key === active,
  );
  useEffect(() => {
    if (!initialSessionKey) {
      setActive(undefined);
      return;
    }
    if (visibleSessions.some((item) => item.session_key === initialSessionKey)) {
      setActive(initialSessionKey);
    }
  }, [initialSessionKey, visibleSessions]);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node || !sessionsQuery.hasNextPage) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          sessionsQuery.hasNextPage &&
          !sessionsQuery.isFetchingNextPage
        ) {
          sessionsQuery.fetchNextPage();
        }
      },
      { root: sessionListRef.current, rootMargin: "80px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [sessionsQuery.hasNextPage, sessionsQuery.isFetchingNextPage, sessionsQuery]);
  const newSession = useMutation({
    mutationFn: () =>
      request<{ session_key: string }>(
        "session/",
        { workspace: workspace.data! },
        {},
      ),
    onSuccess: (data) => {
      const next: Session = {
        session_key: data.session_key,
        name: null,
        first_message: null,
        is_connected: false,
      };
      setSessions((items) => [next, ...items]);
      setActive(next.session_key);
      setQuestion("");
      router.push(
        `/workspace/session/${encodeURIComponent(next.session_key)}`,
      );
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
  const isHydratingActive =
    Boolean(active) &&
    active === initialSessionKey &&
    sessionLookup.isPending &&
    currentTurns.length === 0;
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [currentTurns.length, query.isPending]);
  function ask(text: string) {
    if (!active || !session?.is_connected || !text.trim() || query.isPending)
      return;
    const id = crypto.randomUUID();
    setTurns((previous) => ({
      ...previous,
      [active]: [...(previous[active] || []), { id, question: text.trim() }],
    }));
    setSessions((items) =>
      items.map((item) =>
        item.session_key === active && !item.name && !item.first_message
          ? { ...item, name: text.trim().slice(0, 46) }
          : item,
      ),
    );
    setQuestion("");
    query.mutate({ text: text.trim(), key: active, id });
  }
  return (
    <div
      className={`workspace ${collapsed ? "sidebar-collapsed" : ""} ${isSessionRoute ? "session-route" : ""}`}
    >
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
            !workspace.data || newSession.isPending || query.isPending
          }
        >
          <Plus size={17} />
          New conversation
        </button>
        <div className="sidebar-label">Your conversations</div>
        <div className="session-list" ref={sessionListRef}>
          {visibleSessions.map((item) => (
            <button
              key={item.session_key}
              className={active === item.session_key ? "active" : ""}
              onClick={() => {
                setActive(item.session_key);
                setQuestion("");
                if (window.matchMedia("(max-width: 540px)").matches)
                  setCollapsed(true);
                router.push(
                  `/workspace/session/${encodeURIComponent(item.session_key)}`,
                );
              }}
            >
              <MessageSquare size={16} />
              <span>{sessionDisplayName(item)}</span>
            </button>
          ))}
          {sessionsQuery.hasNextPage && (
            <div ref={sentinelRef} className="session-list-sentinel">
              {sessionsQuery.isFetchingNextPage && (
                <LoaderCircle size={16} className="spin" />
              )}
            </div>
          )}
        </div>
      </aside>
      <button
        className="sidebar-backdrop"
        aria-label="Close sidebar"
        tabIndex={-1}
        onClick={() => setCollapsed(true)}
      />
      <main className="workspace-main">
        <header className="workspace-header">
          <div>
            {collapsed && (
              <>
                <button
                  className="icon-button"
                  aria-label="Expand sidebar"
                  onClick={() => setCollapsed(false)}
                >
                  <PanelLeftOpen size={19} />
                </button>
                <Brand />
              </>
            )}
            <strong className="header-db">
              {session?.database || (session?.is_connected ? "Connected" : "Get started")}
            </strong>
            <span className="badge">
              <span
                className={
                  session?.is_connected ? "status-dot" : "status-dot neutral"
                }
              />
              {session?.is_connected ? "Connected" : "No database connected"}
            </span>
          </div>
          <button
            className="icon-button header-new"
            aria-label="New conversation"
            onClick={() => newSession.mutate()}
            disabled={
              !workspace.data || newSession.isPending || query.isPending
            }
          >
            <Plus size={19} />
          </button>
        </header>
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
                  disabled={!workspace.data || newSession.isPending}
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
        ) : !session.is_connected && currentTurns.length === 0 ? (
          isHydratingActive ? (
            <div className="center-state">
              <LoaderCircle className="spin" />
              Opening conversation…
            </div>
          ) : (
            <div className="connection-container">
            <ConnectionForm
              key={session.session_key}
              context={{ workspace: workspace.data!, session: session.session_key }}
              onConnected={(database, type) =>
                setSessions((items) =>
                  items.map((item) =>
                    item.session_key === session.session_key
                      ? { ...item, database, type, is_connected: true }
                      : item,
                  ),
                )
              }
            />
            </div>
          )
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
      {children}
    </div>
  );
}
