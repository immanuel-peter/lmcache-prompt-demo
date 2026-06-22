import { type NextRequest } from "next/server";

// Run on Node and never cache: the proxy must read BACKEND_URL and forward on
// every request. Unlike next.config rewrites (whose destination is frozen into
// the build manifest), a route handler resolves the backend URL at runtime, so
// the same image works wherever BACKEND_URL points.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function backendBase(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

async function proxy(
  request: NextRequest,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const { path } = await ctx.params;
  const { search } = new URL(request.url);
  // Preserve segments verbatim (e.g. the literal colon in `events:ingest`).
  const target = `${backendBase()}/api/${path.join("/")}${search}`;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch (err) {
    return Response.json(
      { detail: `Upstream request failed: ${(err as Error).message}` },
      { status: 502 },
    );
  }

  // Strip hop-by-hop / length headers; fetch already decoded the body, so let
  // the platform recompute these for the response we stream back.
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.delete("transfer-encoding");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as OPTIONS,
  proxy as HEAD,
};
