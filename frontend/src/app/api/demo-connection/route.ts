import { NextRequest, NextResponse } from "next/server";

function demoDbDetails() {
  const host = (process.env.DEMO_DB_HOST || "").trim();
  const database_name = (process.env.DEMO_DB_NAME || "").trim();
  const username = (process.env.DEMO_DB_USERNAME || "").trim();
  const password = process.env.DEMO_DB_PASSWORD || "";
  if (!host || !database_name || !username || !password) return null;
  return {
    database_type: "postgresql",
    host,
    port: Number(process.env.DEMO_DB_PORT || 5432),
    database_name,
    username,
    password,
    ssl_mode: "require",
  };
}

export async function POST(request: NextRequest) {
  const workspace = request.headers.get("X-Workspace-Key");
  const session = request.headers.get("X-Session-Key");
  if (!workspace || !session) {
    return NextResponse.json(
      { detail: "Workspace and session are required." },
      { status: 400 },
    );
  }
  const demoDb = demoDbDetails();
  if (!demoDb) {
    return NextResponse.json(
      { detail: "Demo database is not configured." },
      { status: 503 },
    );
  }
  try {
    const response = await fetch(
      `${(process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/connection/`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Workspace-Key": workspace,
          "X-Session-Key": session,
        },
        body: JSON.stringify(demoDb),
        cache: "no-store",
        signal: AbortSignal.timeout(180_000),
      },
    );
    return new NextResponse(await response.text(), {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          "The database service is unavailable or took too long to respond. Please try again.",
      },
      { status: 503 },
    );
  }
}
