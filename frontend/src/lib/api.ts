import type { Context, Workspace } from "@/types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  context?: Context,
  body?: unknown,
): Promise<T> {
  if (context && !context.workspace) {
    throw new Error("Workspace is not ready yet. Please try again.");
  }
  let response: Response;
  try {
    response = await fetch(`/api/${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(context ? { "X-Workspace-Key": context.workspace } : {}),
        ...(context?.session ? { "X-Session-Key": context.session } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch {
    throw new Error(
      "Could not reach Rowan. Check your connection and try again.",
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : data.errors
            ?.map(
              (e: { field: string; message: string }) =>
                `${e.field}: ${e.message}`,
            )
            .join(" · ") ||
            data.message ||
            "The request failed. Please try again.",
      response.status,
    );
  return data as T;
}
export const storageKey = "rowan.workspace";
let initializing: Promise<string> | null = null;
export function ensureWorkspace() {
  if (!initializing)
    initializing = (async () => {
      const existing = localStorage.getItem(storageKey);
      if (existing) {
        try {
          await request(`workspace/${encodeURIComponent(existing)}`);
          return existing;
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) throw error;
        }
      }
      const data = await request<Workspace>(
        "workspace/",
        undefined,
        { name: "" },
      );
      localStorage.setItem(storageKey, data.workspace_key);
      return data.workspace_key;
    })().finally(() => {
      initializing = null;
    });
  return initializing;
}
