import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: { proxy: string[] } }
) {
  const path = params.proxy.join("/");
  const contentType = request.headers.get("content-type") || "";

  const body = contentType.includes("multipart")
    ? await request.blob()
    : await request.text();

  const response = await fetch(`${BACKEND_URL}/${path}`, {
    method: "POST",
    headers: request.headers,
    body: body as BodyInit,
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: { proxy: string[] } }
) {
  const path = params.proxy.join("/");

  const response = await fetch(`${BACKEND_URL}/${path}`, {
    method: "GET",
    headers: request.headers,
  });

  return new Response(response.body, {
    status: response.status,
    headers: response.headers,
  });
}