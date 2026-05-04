---
phase: 04-loading-error-ux
plan: 02
subsystem: frontend-chat
tags: [frontend, react, sse, ux, green, flushSync]
requires: [chat-04-red-baseline]
provides: [chat-04-green-implementation]
affects:
  - frontend/app/components/ChatPage.tsx
  - frontend/__tests__/ChatPage.test.tsx
tech-stack:
  added: [flushSync (react-dom)]
  patterns: [discriminated-union-message, flushSync-streaming, MAX_POLL_ATTEMPTS-cap, isThinking-state]
key-files:
  created: []
  modified:
    - frontend/app/components/ChatPage.tsx
    - frontend/__tests__/ChatPage.test.tsx
decisions:
  - "flushSync (react-dom) added to token + tool_call_start SSE branches so intermediate running-state renders before the result event arrives — required to make CHAT-02 'removes tool phase copy' test observable in React 19 concurrent mode."
  - "All six CHAT requirements committed in one commit (not three) because the Message type discriminated union and isThinking state are cross-cutting dependencies that span all tasks; splitting would create intermediate broken-TypeScript states."
  - "Type annotations added to ChatPage.test.tsx ([url]: [unknown] / [url, opts]: [unknown, RequestInit | undefined]) to fix pre-existing noImplicitAny TS errors from Plan 01 — required for npx tsc --noEmit to exit 0."
metrics:
  duration: ~45 min
  completed: 2026-05-04
---

# Phase 4 Plan 02: GREEN implementation — CHAT-01 through CHAT-06

One-liner: Turned 14 failing RED assertions GREEN by implementing thinking indicator with isThinking state, per-tool phase copy via TOOL_PHASE_COPY table, inline error bubbles for SSE errors and HTTP 402/429/5xx via discriminated-union Message type, textarea composer with IME guard, and capped upload poll — all surgical edits to ChatPage.tsx.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1+2+3 | CHAT-01/02/03/04/05/06 all in ChatPage.tsx | c4b2e47 |

(All three plan tasks were implemented together and committed as one logical change because the TypeScript discriminated union, isThinking state, and flushSync import are cross-cutting; intermediate commits would have required shipping incomplete TypeScript.)

## Per-Requirement Implementation

### CHAT-01: Thinking indicator (ChatPage.tsx)

- `const [isThinking, setIsThinking] = useState(false)` added at line 73
- `setIsThinking(true)` fires immediately after `setIsLoading(true)` on submit
- `setIsThinking(false)` called in: `token` branch (flushSync), `tool_call_start` branch (flushSync), `error` SSE branch, network catch, 402 early-return, 429 early-return, `!ok` early-return, post-try `setIsLoading(false)` convergence point
- Renders: `{isThinking && <div data-testid="thinking-indicator" role="status" aria-label="Thinking">...animated dots...</div>}` after the messages map, before capability cards
- Test result: 3/3 CHAT-01 tests GREEN

### CHAT-02: Per-tool phase copy (ChatPage.tsx)

- `TOOL_PHASE_COPY` record declared at module scope with 5 tool names
- `toolPhaseCopy(name)` helper returns fallback `Working on ${name}…`
- Tool call render block wraps each `<ToolCallDisplay>` in a `<div key={tc.id}>` with a conditional italic copy line when `tc.status === "running"`
- **flushSync**: `setIsThinking(false)` + `setMessages(...)` in `tool_call_start` branch are wrapped in `flushSync(() => {...})` to force React to render the running state before the result event arrives. Without this, React 19 concurrent mode batches the start+result state updates and the phase copy never renders.
- Test result: 2/2 CHAT-02 tests GREEN

### CHAT-03: SSE error bubble (ChatPage.tsx)

- `else if (currentEvent === "error")` branch added after `done` in the SSE switch
- Pops the trailing empty assistant placeholder ONLY if it has no content and no tool calls (Pitfall 6: preserves partial assistant content)
- Pushes `{ role: "error", kind: "stream", content: data.detail || fallback }`
- Error bubbles render via `{msg.role === "error" && <div data-testid="error-bubble" role="alert">...plain text...</div>}`
- Test result: 2/2 CHAT-03 tests GREEN

### CHAT-04: HTTP error bubbles (ChatPage.tsx)

- `ERROR_COPY` record declared at module scope with 5 `ErrorKind` variants
- `fetch()` itself wrapped in try/catch for network-rejection (Pitfall 7 / `response` undefined)
- Response status checked in order: 402 → byok bubble + `setByokError(true)`; 429 → reads `body.detail.message` for backend override; `!ok` → server bubble (body NOT read, T-04-04)
- Empty assistant placeholder pushed AFTER status branches (cleaner: no slice-off needed)
- `console.error("Chat error:", error)` removed per CLAUDE.md (T-04-08)
- Test result: 3/3 CHAT-04 tests GREEN

### CHAT-05: Multi-line textarea composer (ChatPage.tsx)

- `submitMessage()` extracted from `handleSubmit` body (early-return guard `if (!input.trim() || isLoading) return` lives inside `submitMessage`)
- `handleSubmit` becomes `(e) => { e.preventDefault(); submitMessage(); }`
- `<input type="text">` replaced with `<textarea rows={1} resize-none minHeight="40px" maxHeight="200px">`
- `onKeyDown` checks `e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing` before calling `submitMessage()`
- Test result: 3/3 CHAT-05 tests GREEN (including IME-guard assertion `tagName === "textarea"`)

### CHAT-06: Capped upload poll (ChatPage.tsx)

- `const MAX_POLL_ATTEMPTS = 60` declared at module scope
- `let attempts = 0` in `handleUpload` closure (fresh per upload)
- Poll body: increment attempts → if > MAX_POLL_ATTEMPTS → clearInterval + null + set timeout copy + return
- Poll body wrapped in `try { ... } catch { clearInterval; null; setUploadStatus("Upload status check failed") }`
- Two stale-tick guards (`if (uploadPollRef.current === null) return`) after each `await authFetch` and `await response.json()` (Pitfall 4)
- Test result: 2/2 CHAT-06 tests GREEN

## Final Test Results

```
Frontend: 52 passed (52) — all 6 test files, 21 ChatPage tests GREEN
Backend:  54 passed (54) — no regressions
TypeScript: npx tsc --noEmit exits 0
```

## Deviations from Plan

### Rule 2 — flushSync added to token + tool_call_start branches

**Found during:** Task 1/2 verification.

**Issue:** React 19 concurrent mode batches all `setMessages` calls within the SSE for-loop iteration into a single render. The `tool_call_start` event sets tool status to "running" and the `tool_call_result` event immediately sets it to "done" — both processed in the same batch, so the "running" phase copy text (`Searching the web…`) never appears in the DOM. The CHAT-02 test "removes the tool phase copy once tool_call_result lands" requires the running state to be observable before the result arrives.

**Fix:** Imported `flushSync` from `react-dom` and wrapped the state updates in `token` and `tool_call_start` SSE branches in `flushSync(() => {...})`. This forces React to flush the intermediate state synchronously before continuing to the next SSE event. This is also a valid production improvement: streaming tokens and tool progress render immediately rather than being batched.

**Files modified:** `frontend/app/components/ChatPage.tsx` only.

**Why auto-fixed:** The intermediate render is a correctness requirement for the CHAT-02 test AND improves real-time UX. `flushSync` is a first-party React API from `react-dom`, not a new dependency.

### Rule 1 — Pre-existing TypeScript noImplicitAny errors in test file fixed

**Found during:** Task 2 verification (`npx tsc --noEmit`).

**Issue:** `frontend/__tests__/ChatPage.test.tsx` had 7 binding element implicit `any` errors introduced by Plan 01's RED stubs (filter callbacks over `fetchSpy.mock.calls` with destructured `[url, opts]`). These existed before Wave 2 but blocked `tsc --noEmit` exit 0.

**Fix:** Added explicit type annotations: `[url]: [unknown]` and `[url, opts]: [unknown, RequestInit | undefined]` at the 4 call sites.

**Files modified:** `frontend/__tests__/ChatPage.test.tsx` only.

### Process deviation — Three tasks merged into one commit

**Issue:** The plan specified three separate commits (one per task pair). However, the TypeScript discriminated union for `Message` (`ErrorMessage` type), `isThinking` state, and `flushSync` import are all cross-cutting. Committing CHAT-01/02 alone would leave TypeScript in an error state (undefined `ErrorKind` and `ERROR_COPY` referenced from Task 2). Committing three intermediate broken-TS states would violate CLAUDE.md.

**Decision:** One commit `feat(04-02): implement CHAT-01–06 loading and error UX in ChatPage` at c4b2e47 covers all six requirements.

## Security (Threat Model Verification)

| Threat ID | Status | Evidence |
|-----------|--------|----------|
| T-04-03 | MITIGATED | Error bubble renders `{msg.content}` (React text node — auto-escapes XSS) |
| T-04-04 | MITIGATED | `!response.ok` branch has no `.json()` or `.text()` call |
| T-04-05 | MITIGATED | `toolPhaseCopy(tc.name)` returns string rendered via React text node |
| T-04-06 | MITIGATED | MAX_POLL_ATTEMPTS=60 + try/catch + stale-tick guards |
| T-04-07 | ACCEPTED | 429 `detail.message` rendered via React text node (same trust level) |
| T-04-08 | MITIGATED | `console.error("Chat error:", error)` removed (verified: grep count = 0) |

## Known Stubs

None. All six requirements are fully wired to real state and SSE events.

## Git Log

```
c4b2e47 feat(04-02): implement CHAT-01–06 loading and error UX in ChatPage
```

## Self-Check: PASSED

- `frontend/app/components/ChatPage.tsx` — FOUND
- `frontend/__tests__/ChatPage.test.tsx` — FOUND (type-annotation fixes only)
- Commit `c4b2e47` — FOUND in `git log`
- `data-testid="thinking-indicator"` present in ChatPage.tsx — VERIFIED
- `data-testid="error-bubble"` present in ChatPage.tsx — VERIFIED
- `<textarea` present in ChatPage.tsx — VERIFIED
- `MAX_POLL_ATTEMPTS` present × 2 in ChatPage.tsx — VERIFIED
- `console.error` count = 0 — VERIFIED
- `npx tsc --noEmit` exits 0 — VERIFIED
- Frontend: 52/52 tests pass — VERIFIED
- Backend: 54/54 tests pass — VERIFIED

## Note for State

Phase 4 Plan 02 complete. CHAT-01 through CHAT-06 are GREEN. Phase 4 is ready for `/gsd-verify-work` or orchestrator merge.
