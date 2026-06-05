import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL || "http://localhost:8000";
const API_KEY = process.env.API_KEY || "";

type RouteContext = { params: Promise<{ path: string[] }> };

async function handler(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const targetPath = path.join("/");

  const url = new URL(`${API_URL}/${targetPath}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const forwardHeaders = new Headers();
  forwardHeaders.set("X-API-Key", API_KEY);

  const contentType = request.headers.get("content-type");
  if (contentType) forwardHeaders.set("content-type", contentType);

  const accept = request.headers.get("accept");
  if (accept) forwardHeaders.set("accept", accept);

  const init: RequestInit = { method: request.method, headers: forwardHeaders };

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    // @ts-expect-error duplex is required for streaming request bodies in Node 18+
    init.duplex = "half";
  }

  const upstream = await fetch(url.toString(), init);

  const responseHeaders = new Headers();
  const upstreamType = upstream.headers.get("content-type");
  if (upstreamType) responseHeaders.set("content-type", upstreamType);

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const DELETE = handler;
export const PATCH = handler;
