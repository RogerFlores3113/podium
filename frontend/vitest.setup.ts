import "@testing-library/react/pure";
import { afterEach, vi } from "vitest";
import { configure } from "@testing-library/react";

// Ensure fake timers are always restored between tests, even if a test fails
// before calling vi.useRealTimers(). Without this, a failing test that calls
// vi.useFakeTimers() would leave fake timers active for all subsequent tests,
// causing waitFor() to hang (since it uses setInterval internally).
afterEach(() => {
  vi.useRealTimers();
});

// Configure testing-library to advance fake timers during async utility polling.
// This enables waitFor() to work correctly when vi.useFakeTimers() is active,
// because waitFor() uses setInterval internally and needs timers to advance.
configure({
  unstable_advanceTimersWrapper(cb) {
    return vi.advanceTimersByTimeAsync(1);
  },
  asyncWrapper: async (cb) => {
    // Repeatedly advance fake timers while waiting for async operations
    const result = await cb();
    return result;
  },
});
