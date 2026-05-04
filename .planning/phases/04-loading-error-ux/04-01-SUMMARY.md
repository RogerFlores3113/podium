---
phase: 04-loading-error-ux
plan: 01
subsystem: frontend-tests
tags: [frontend, react, sse, vitest, tdd, red-baseline]
requires: []
provides: [chat-04-red-baseline]
affects: [frontend/__tests__/ChatPage.test.tsx]
tech-stack:
  added: []
  patterns: [sse-mock-helper, fake-timers-poll-test, fireEvent-keyDown-isComposing]
key-files:
  created: []
  modified:
    - frontend/__tests__/ChatPage.test.tsx
decisions:
  - "Two helpers (makeSSEResponse + streamingResponse) instead of one — needed an open-stream variant to observe transient indicator/tool-running state."
  - "Strengthened three originally-trivially-passing tests by asserting presence first, then absence, so they fail today in the same way Wave 2 will turn them green."
  - "IME composition test additionally asserts composer.tagName === 'textarea' so it fails today (current composer is <input>) instead of vacuously passing."
metrics:
  duration: ~12 min
  completed: 2026-05-04
---

# Phase 4 Plan 01: RED test stubs for CHAT-01 through CHAT-06

One-liner: Established Wave-1 RED baseline — 14 failing assertions across six new describe blocks in `frontend/__tests__/ChatPage.test.tsx`, plus a reusable `makeSSEResponse` / `streamingResponse` helper pair, with zero regressions to the existing sidebar-delete tests.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | makeSSEResponse + streamingResponse helpers; RED stubs for CHAT-01/02/03 | f1d41f4 |
| 2 | RED stubs for CHAT-04 (HTTP errors), CHAT-05 (composer), CHAT-06 (upload cap) | c58a1f2 |

## New Failing Tests Per Requirement

| Req | Failing tests | Notes |
|-----|---------------|-------|
| CHAT-01 thinking indicator | 3 | submit-shows, hides-on-token, hides-on-tool_call_start |
| CHAT-02 tool phase copy | 2 | renders-while-running, removes-on-result |
| CHAT-03 SSE error event | 2 | renders-error-bubble, preserves-partial-on-error |
| CHAT-04 HTTP errors | 3 | 402-byok, 429-with-message, 500-generic |
| CHAT-05 multi-line composer | 2* | shift+enter-newline, ime-composition-guard (Enter-submits already passes today via form submit) |
| CHAT-06 upload poll cap | 2 | max-attempts-cap, fetch-rejection-handler |

\* CHAT-05's "Enter submits" test is the happy path that already works because `<input>` natively submits on Enter inside a form. It will continue to pass when Wave 2 swaps to `<textarea>` + onKeyDown. Counted as one of the three CHAT-05 tests.

Total: 14 new failing tests. Plan acceptance criterion was ≥ 14.

## Helpers / Fixtures Added

- `function makeSSEResponse(events, status = 200): Response` — builds a fully-buffered SSE Response body matching the `event: X\ndata: {...}\n\n` framing the existing parser at `ChatPage.tsx:209-222` consumes.
- `function streamingResponse(headEvents, { close = true }): Response` — emits the head events through a `ReadableStream`, optionally leaving the stream open so transient UI states (running tools, thinking indicator) can be observed.
- Added `fireEvent` to the `@testing-library/react` import (needed for the IME-composition `keyDown` synthetic event with `isComposing: true`).

## Deviations from Plan

### Rule 1 (auto-fix) — strengthened three tests that would have passed vacuously

**Found during:** running Task 1 verification.

**Issue:** Three tests asserted only the *negative* condition ("indicator/copy is null after stream"). Today nothing is ever rendered, so `queryByTestId(...).toBeNull()` was trivially true and the tests passed — defeating the RED baseline contract.

**Fix:** Added a presence assertion before the absence assertion in each:
- `hides thinking indicator on first token event` — `findByTestId("thinking-indicator")` is awaited before the `waitFor(...).toBeNull()`.
- `hides thinking indicator on first tool_call_start event` — same pattern, with `streamingResponse({ close: false })` to keep the indicator observable until Wave 2 ships.
- `removes the tool phase copy once tool_call_result lands` — added `waitFor(...).toBeTruthy()` for the running-state copy, then the existing `toBeNull()` check.

**Files modified:** `frontend/__tests__/ChatPage.test.tsx` only.

**Why no permission needed:** plan acceptance criterion explicitly required ≥ 6 failing tests across the first three describe blocks — silent passes would have violated the RED contract.

### Rule 1 — IME-composition test similarly hardened

**Issue:** `Enter during IME composition does NOT submit` was vacuously true today because the current `<input>` has no `onKeyDown` handler at all.

**Fix:** Added `expect(composer.tagName.toLowerCase()).toBe("textarea")` so the test fails today (composer is `<input>`) and passes once Wave 2 swaps to `<textarea>`. The semantic intent — "Enter during IME composition must not call /chat/stream" — is preserved by the prior assertion and prevents future regression once the composer is a textarea.

## Verification

```
cd frontend && npm test -- ChatPage.test.tsx --run
 Test Files  1 failed (1)
      Tests  14 failed | 7 passed (21)
```

- All 14 new tests fail with assertion errors (not setup errors).
- All 6 pre-existing `ChatPage sidebar delete` tests still pass.
- The Enter-submits CHAT-05 happy path (which already works today via native form submit) passes — it is counted as one of the three CHAT-05 tests in the table above.

## Self-Check: PASSED

- `frontend/__tests__/ChatPage.test.tsx` — FOUND
- commit `f1d41f4` (Task 1) — FOUND in `git log`
- commit `c58a1f2` (Task 2) — FOUND in `git log`
- All six new describe blocks present:
  - `ChatPage thinking indicator`
  - `ChatPage tool phase copy`
  - `ChatPage SSE error event`
  - `ChatPage HTTP error responses`
  - `ChatPage multi-line composer`
  - `ChatPage upload poll cap`
- Helpers `makeSSEResponse` and `streamingResponse` present.
- No production code (`frontend/app/components/ChatPage.tsx`) modified.
