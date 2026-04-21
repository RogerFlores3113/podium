import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { formatRelativeTime } from "@/app/utils/time";

describe("formatRelativeTime", () => {
  const NOW = new Date("2025-01-15T12:00:00Z").getTime();

  beforeEach(() => {
    vi.spyOn(Date, "now").mockReturnValue(NOW);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns 'just now' for timestamps less than 1 minute ago", () => {
    const iso = new Date(NOW - 30_000).toISOString(); // 30 seconds ago
    expect(formatRelativeTime(iso)).toBe("just now");
  });

  it("returns minutes for timestamps under 1 hour", () => {
    const iso = new Date(NOW - 5 * 60_000).toISOString(); // 5 minutes ago
    expect(formatRelativeTime(iso)).toBe("5m ago");
  });

  it("returns hours for timestamps under 24 hours", () => {
    const iso = new Date(NOW - 3 * 60 * 60_000).toISOString(); // 3 hours ago
    expect(formatRelativeTime(iso)).toBe("3h ago");
  });

  it("returns days for timestamps under 7 days", () => {
    const iso = new Date(NOW - 2 * 24 * 60 * 60_000).toISOString(); // 2 days ago
    expect(formatRelativeTime(iso)).toBe("2d ago");
  });

  it("returns a date string for timestamps 7+ days ago", () => {
    const old = new Date(NOW - 10 * 24 * 60 * 60_000); // 10 days ago
    const result = formatRelativeTime(old.toISOString());
    expect(result).toBe(old.toLocaleDateString());
  });

  it("returns '1m ago' at exactly 1 minute", () => {
    const iso = new Date(NOW - 60_000).toISOString();
    expect(formatRelativeTime(iso)).toBe("1m ago");
  });
});
