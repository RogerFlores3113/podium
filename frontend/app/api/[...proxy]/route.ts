import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

function forwardHeaders(request: NextRequest): Headers {
  const headers = new Headers(request.headers);
  // Strip the incoming host header so the backend sees its own hostname,
  // not the public Next.js hostname.
  headers.delete("host");
  return headers;
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> }
) {
  const { proxy } = await params;
  const path = proxy.join("/");
  const contentType = request.headers.get("content-type") || "";

  const body = contentType.includes("multipart")
    ? await request.blob()
    : await request.text();

  const response = await fetch(`${BACKEND_URL}/${path}`, {
    method: "POST",
    headers: forwardHeaders(request),
    body: body as BodyInit,
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> }
) {
  const { proxy } = await params;
  const path = proxy.join("/");
  const search = request.nextUrl.search;

  const response = await fetch(`${BACKEND_URL}/${path}${search}`, {
    method: "GET",
    headers: forwardHeaders(request),
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> }
) {
  const { proxy } = await params;
  const path = proxy.join("/");
  const search = request.nextUrl.search;

  const response = await fetch(`${BACKEND_URL}/${path}${search}`, {
    method: "DELETE",
    headers: forwardHeaders(request),
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ proxy: string[] }> }
) {
  const { proxy } = await params;
  const path = proxy.join("/");
  const contentType = request.headers.get("content-type") || "";

  const body = contentType.includes("multipart")
    ? await request.blob()
    : await request.text();

  const response = await fetch(`${BACKEND_URL}/${path}`, {
    method: "PATCH",
    headers: forwardHeaders(request),
    body: body as BodyInit,
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}