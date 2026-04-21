import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";

// Mock Clerk's useAuth
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("test-token-123"),
  }),
}));

describe("useAuthFetch", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("ok", { status: 200 }));
  });

  it("attaches Authorization header with Bearer token", async () => {
    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer test-token-123",
        }),
      })
    );
  });

  it("merges caller-supplied headers with the Authorization header", async () => {
    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/stream",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer test-token-123",
        }),
      })
    );
  });

  it("returns the fetch Response", async () => {
    const { result } = renderHook(() => useAuthFetch());
    const res = await result.current("https://api.example.com/health");
    expect(res.status).toBe(200);
  });
});
