import { DEMO_MODE } from "./preview";

/** Demo input never leaves the browser. Server routes independently block upstreams. */
export async function previewFetch(input: string, init?: RequestInit): Promise<Response> {
  if (!DEMO_MODE) return fetch(input, init);
  init?.signal?.throwIfAborted();
  const { demoResponse } = await import("./demo-api");
  const url = new URL(input, "https://demo.invalid");
  const path = url.pathname.replace(/^\/api\//, "").split("/");
  // Do not pass the caller's body or headers, even to the in-memory handler.
  return demoResponse(new Request(url, { method: init?.method ?? "GET" }), path);
}
