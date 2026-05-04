---
phase: 08-frontend-bugs-polish
plan: "01"
subsystem: frontend
tags: [ui-fixes, ux, chatpage, clerk-auth, byok, tool-calls]
dependency_graph:
  requires: []
  provides: [UI-01, UI-02, UI-03, UI-04, DEBT-03, UX-01, UX-02]
  affects: [frontend/app/components/ChatPage.tsx]
tech_stack:
  added: []
  patterns:
    - useAuth() from @clerk/nextjs for reactive auth state
    - flushSync reserved for tool_call_start only (not tool_call_result)
    - byokCopy state mirrors ERROR_COPY.byok, updated on 402
key_files:
  created: []
  modified:
    - frontend/app/components/ChatPage.tsx
    - frontend/__tests__/ChatPage.test.tsx
decisions:
  - Use toBeNull/toBeTruthy not toBeInTheDocument (no jest-dom in project)
  - tool_call_result handler: setIsThinking(true) without flushSync to preserve observability of running-state in tests
  - "#b91c1c" retained in error bubble style (semantic red for error messages); only removed from delete button
  - synthesis gap test uses streamingResponse(close:false) so thinking indicator is observable before stream ends
metrics:
  duration: ~30 minutes
  completed: "2026-05-04"
  tasks: 2
  files: 2
---

# Phase 8 Plan 01: Frontend Bug Fixes & Polish Summary

**One-liner:** Seven targeted ChatPage.tsx fixes covering delete button styling, hamburger desktop-hide, reactive guest cleanup on sign-in, Generate images card removal, provider-correct BYOK 402 error copy, synthesis-gap thinking indicator, and TOOL_PHASE_COPY audit.

## What Was Built

Applied 7 fixes to `frontend/app/components/ChatPage.tsx` covering all requirements in this plan (UI-01 through UX-02). Added 5 new tests covering the changed behaviors.

### Changes Applied

**UI-01 — Delete button bubble styling**
- Changed `absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6` to `absolute top-1 right-1 w-5 h-5 rounded-full`
- Removed hardcoded `color: "#b91c1c"`, replaced with `background: var(--bg-elevated), color: var(--text-muted)`
- Result: circular badge at true top-right of card, dark/light mode via CSS vars

**UI-02 — Hamburger desktop-hide**
- Added `md:hidden` to hamburger button className
- Hamburger is now invisible on md+ breakpoints where sidebar is always-visible

**UI-03 — Reactive guest cleanup on sign-in**
- Imported `useAuth` from `@clerk/nextjs`
- Added `const { isSignedIn } = useAuth()` in component body
- Added `useEffect([isSignedIn, fetchConversations])` that calls `setIsGuest(false)`, clears sessionStorage guest tokens, and refreshes conversation list when Clerk confirms sign-in

**UI-04 — Remove Generate images capability card**
- Deleted `{ icon: "🎨", label: "Generate images", ... }` from `CAPABILITY_CARDS`
- Array now has 5 entries

**DEBT-03 — Provider-correct BYOK 402 error copy**
- Changed `ERROR_COPY.byok` fallback to generic: `"Add your API key in Settings to chat. Or sign out and try Podium as a guest."`
- Added `byokCopy` state (initialized to `ERROR_COPY.byok`)
- 402 handler now calls `setByokCopy(copy)` in addition to pushing to messages
- `byokError` persistent banner replaced hardcoded "Add your OpenAI API key..." with `{byokCopy}` state variable

**UX-01 — Synthesis gap thinking indicator**
- Added `setIsThinking(true)` in the `tool_call_result` SSE event handler
- Placed after `setMessages(status=done)` but before `setMessages(new empty assistant)`
- Uses standard (non-flushSync) state update to preserve test observability of running state

**UX-02 — TOOL_PHASE_COPY audit**
- Audit confirmed all 5 entries are ≤3 words (excluding trailing ellipsis)
- Added comment: `// UX-02 audit passed: all entries ≤3 words (excluding trailing ellipsis)`
- No values changed

### Tests Added (5 new, all GREEN)

| Test | Requirement | Description |
|------|-------------|-------------|
| hamburger button > has md:hidden class | UI-02 | Asserts `hamburger.className.toContain("md:hidden")` |
| guest banner reactive cleanup > clears guest state when isSignedIn becomes true | UI-03 | Sets sessionStorage guest tokens, verifies banner present, toggles mockIsSignedIn to true, verifies banner gone |
| capability cards > does not include Generate images card | UI-04 | `queryByText("Generate images").toBeNull()` |
| ChatPage BYOK provider-correct copy > shows provider-correct copy | DEBT-03 | 402 with `detail.message: "Add your Anthropic API key..."` → text appears in DOM |
| synthesis gap indicator > shows thinking indicator after tool_call_result | UX-01 | Streaming open after tool_call_result; confirms thinking indicator visible |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] toBeInTheDocument not available**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** The plan's test code used `toBeInTheDocument()` assertions; however this matcher is from `@testing-library/jest-dom` which is NOT installed in this project. Assertions failed with "Invalid Chai property: toBeInTheDocument".
- **Fix:** Replaced all `toBeInTheDocument()` with `toBeTruthy()`, all `not.toBeInTheDocument()` with `toBeNull()` in the new tests.
- **Files modified:** `frontend/__tests__/ChatPage.test.tsx`
- **Commit:** e1b12fb

**2. [Rule 1 - Bug] flushSync in tool_call_result broke pre-existing test**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** The plan specified wrapping `setMessages(done)` + `setIsThinking(true)` in `flushSync()`. This caused the "removes the tool phase copy once tool_call_result lands" pre-existing test to fail because `flushSync` made the status transition synchronous, preventing `waitFor` from observing the "running" state.
- **Fix:** Removed `flushSync` wrapper from `tool_call_result` handler. `setIsThinking(true)` is called without `flushSync` (React batches it with subsequent `setMessages`). The effect (thinking indicator visible during synthesis gap) is preserved.
- **Files modified:** `frontend/app/components/ChatPage.tsx`
- **Commit:** e1b12fb

**3. [Rule 1 - Bug] UX-01 test stream needed to stay open**
- **Found during:** Task 2 (GREEN phase)
- **Issue:** Test used a plain `Response(sseBody)` that closes after all events. When stream closes, `setIsThinking(false)` fires at end of `submitMessage`, making the thinking indicator invisible before `waitFor` can poll.
- **Fix:** Changed test to use `streamingResponse([...], { close: false })` so the stream stays open and the thinking indicator state is observable.
- **Files modified:** `frontend/__tests__/ChatPage.test.tsx`
- **Commit:** e1b12fb

**4. [Minor] `#b91c1c` remains in error bubble**
- **Found during:** Task 2 acceptance criteria check
- **Issue:** Plan's grep criterion `grep -c '#b91c1c' ... returns 0` cannot be met because the error message bubble (role="error" messages) correctly uses `color: "#b91c1c"` for semantic red error text.
- **Decision:** Kept the error bubble red. The plan's intent was to remove `#b91c1c` from the **delete button** (done). The error bubble's red color is correct and intentional.

## Known Stubs

None. All changes wire real data sources.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: info-disclosure | ChatPage.tsx | `byokCopy` echoes 402 body.detail.message — mitigated: body comes from our own backend, provider label is not sensitive (T-08-02 already accepted) |

## Self-Check: PASSED

- FOUND: frontend/app/components/ChatPage.tsx
- FOUND: frontend/__tests__/ChatPage.test.tsx
- FOUND: .planning/phases/08-frontend-bugs-polish/08-01-SUMMARY.md
- FOUND commit 29890b0 (test RED baseline)
- FOUND commit e1b12fb (all 7 fixes + GREEN tests)
- 57 tests passing (verified by test run)
