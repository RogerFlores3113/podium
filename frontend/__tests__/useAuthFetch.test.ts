import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("clerk-token-123"),
  }),
}));

describe("useAuthFetch", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("ok", { status: 200 }));
    sessionStorage.clear();
  });

  afterEach(() => {
    sessionStorage.clear();
  });

  it("attaches Authorization header with Clerk Bearer token", async () => {
    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer clerk-token-123",
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
          Authorization: "Bearer clerk-token-123",
        }),
      })
    );
  });

  it("returns the fetch Response", async () => {
    const { result } = renderHook(() => useAuthFetch());
    const res = await result.current("https://api.example.com/health");
    expect(res.status).toBe(200);
  });

  it("uses guest token from sessionStorage when present and unexpired", async () => {
    const futureDate = new Date(Date.now() + 60 * 60 * 1000).toISOString();
    sessionStorage.setItem("podium_guest_token", "guest-jwt-token");
    sessionStorage.setItem("podium_guest_expires", futureDate);

    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer guest-jwt-token",
        }),
      })
    );
  });

  it("falls back to Clerk token when guest token is expired", async () => {
    const pastDate = new Date(Date.now() - 1000).toISOString();
    sessionStorage.setItem("podium_guest_token", "expired-guest-token");
    sessionStorage.setItem("podium_guest_expires", pastDate);

    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer clerk-token-123",
        }),
      })
    );
  });

  it("falls back to Clerk token when no guest token is set", async () => {
    const { result } = renderHook(() => useAuthFetch());
    await result.current("https://api.example.com/chat/");

    expect(fetch).toHaveBeenCalledWith(
      "https://api.example.com/chat/",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer clerk-token-123",
        }),
      })
    );
  });
});
