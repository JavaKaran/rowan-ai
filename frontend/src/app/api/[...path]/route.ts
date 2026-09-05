import { NextRequest, NextResponse } from "next/server";
const allowed =
  /^(workspace\/(?:[\w-]+)?|session\/(?:[\w-]+)?|connection|query)$/;
async function proxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const endpoint = path.join("/").replace(/\/$/, "");
  if (!allowed.test(endpoint))
    return NextResponse.json({ detail: "Endpoint not found" }, { status: 404 });
  const headers = new Headers({ "Content-Type": "application/json" });
  for (const name of ["X-Workspace-Key", "X-Session-Key"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const response = await fetch(
      `${(process.env.BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/${endpoint}/`,
      {
        method: request.method,
        headers,
        ...(request.method === "POST" ? { body: await request.text() } : {}),
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
export { proxy as GET, proxy as POST };
