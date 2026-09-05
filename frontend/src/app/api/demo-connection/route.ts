import { NextRequest, NextResponse } from "next/server";

// Demo database details for the "try the demo" CTA. This route runs
// server-side only, so these credentials are never sent to the browser.
const DEMO_DB = {
  database_type: "postgresql",
  host: "ep-cold-fire-aw2fywl8-pooler.c-12.us-east-1.aws.neon.tech",
  port: 5432,
  database_name: "products",
  username: "products_owner",
  password: "npg_MySCBDI4O7Vj",
  ssl_mode: "require",
};

export async function POST(request: NextRequest) {
  const workspace = request.headers.get("X-Workspace-Key");
  const session = request.headers.get("X-Session-Key");
  if (!workspace || !session) {
    return NextResponse.json(
      { detail: "Workspace and session are required." },
      { status: 400 },
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
        body: JSON.stringify(DEMO_DB),
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
