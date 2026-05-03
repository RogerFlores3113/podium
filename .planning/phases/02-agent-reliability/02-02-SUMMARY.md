---
phase: 02-agent-reliability
plan: 02
subsystem: agent
tags: [agent, litellm, openai-responses-api, tavily, web-search, tdd, green-phase]

dependency_graph:
  requires:
    - phase: 02-01
      provides: tests/test_agent_reliability.py with 11 RED tests for AGENT-01/02/03/QUAL-02/03/04
  provides:
    - AGENT_SYSTEM_PROMPT synthesis mandate (AGENT-01)
    - Empty-completion retry with nudge in litellm path (AGENT-02)
    - Empty-completion retry in Responses API path (AGENT-02)
    - Tavily exception sanitization in web_search.py (AGENT-03)
  affects:
    - 02-03 (QUAL-02/03/04 — the remaining 3 failing tests)
    - 04-loading-error-ux (agent reliability improves chat UX)

tech-stack:
  added: []
  patterns:
    - Empty-completion guard before no-tool-call branch with iteration==0 retry
    - Tavily errors imported from tavily.errors directly (not tavily.__init__)
    - exc_info=True on all exception handlers, never str(e) of auth errors in return

key-files:
  created: []
  modified:
    - app/services/agent.py
    - app/tools/web_search.py

key-decisions:
  - "Synthesis mandate appended at end of AGENT_SYSTEM_PROMPT, not replacing — avoids breaking existing instruction flow"
  - "Retry guard placed BEFORE the no-tool-call branch so it fires only on empty completions, not partial text with no tool calls"
  - "Responses API retry appended nudge as user message with input_text content type (matching the Responses API input format)"
  - "TavilyTimeoutError aliased from tavily.errors.TimeoutError to avoid shadowing Python built-in TimeoutError"
  - "BadRequestError handler returns query text (user-supplied, safe) but not str(e) — avoids internal state leakage"

patterns-established:
  - "Tavily error pattern: import specific exceptions from tavily.errors, use exc_info=True, return generic user-safe strings"
  - "Agent empty-completion pattern: guard on iteration==0 with nudge retry, fallback string on subsequent iterations"

requirements-completed:
  - AGENT-01
  - AGENT-02
  - AGENT-03

duration: 12min
completed: 2026-05-03
---

# Phase 2 Plan 02: Agent Reliability GREEN Implementation Summary

**Synthesis mandate in AGENT_SYSTEM_PROMPT, empty-completion retry in both LLM paths, and sanitized Tavily exception handling — 8 new tests GREEN, 48 total passing**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-05-03T22:20:00Z
- **Completed:** 2026-05-03T22:32:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Appended IMPORTANT tool synthesis rule block to AGENT_SYSTEM_PROMPT with MUST language (AGENT-01)
- Added empty-completion guard to litellm loop: retries once with nudge on iteration 0, yields fallback string on second empty (AGENT-02)
- Added empty-completion guard to Responses API loop: same retry/fallback pattern inside `if not pending_calls:` block (AGENT-02)
- Wrapped `AsyncTavilyClient.search()` with 5 specific exception handlers from `tavily.errors` plus catch-all (AGENT-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add synthesis mandate to AGENT_SYSTEM_PROMPT (AGENT-01)** - `4e688c6` (feat)
2. **Task 2: Add empty-completion retry to litellm and Responses API paths (AGENT-02)** - `5ed1b3a` (feat)
3. **Task 3: Wrap Tavily client.search() with sanitizing exception handlers (AGENT-03)** - `ca264ad` (feat)

**Plan metadata:** (docs commit — separate)

## Files Created/Modified

- `app/services/agent.py` — Synthesis mandate appended to AGENT_SYSTEM_PROMPT; empty-completion guard inserted before `if not accumulated_tool_calls:` in litellm loop; retry logic added inside `if not pending_calls:` in Responses API loop
- `app/tools/web_search.py` — Added 6 imports from `tavily.errors`; wrapped `client = AsyncTavilyClient(...)` and `client.search(...)` in try/except with 5 specific handlers plus catch-all

## Decisions Made

- Synthesis mandate appended at end of existing AGENT_SYSTEM_PROMPT constant rather than replacing it — preserves all existing instructions, only adds new block
- Empty-completion guard placed before the `if not accumulated_tool_calls:` branch so it only fires when BOTH text and tool calls are absent (truly empty), not when model returns text without tools
- For Responses API, guard placed inside `if not pending_calls:` block and checks `accumulated_text.strip()` after the `assistant_message` emit already happened — avoids duplicate emit on fallback path
- TavilyTimeoutError aliased from `tavily.errors.TimeoutError` (not `tavily.__init__`) because ForbiddenError and TimeoutError are not re-exported from the top-level tavily package

## Deviations from Plan

None — plan executed exactly as written. All three tasks matched the provided code snippets precisely.

The one deviation discovered (not a blocker): the plan's verification section predicted "2 still-failing" tests (QUAL-03 and QUAL-04) but actually 3 remain failing (QUAL-02 also remains). This was already true in Plan 01's RED baseline — QUAL-02, QUAL-03, and QUAL-04 are all addressed in Plan 03.

## Issues Encountered

Tests required env vars (DATABASE_URL, OPENAI_API_KEY) to be set before running — the worktree's pytest invocation needed `source /home/rflor/podium/.env` because pydantic Settings validates required fields on import. This is expected behavior for this project's test setup.

## Known Stubs

None — no production stubs introduced. All exception handlers return complete user-safe strings.

## Threat Flags

No new attack surface introduced beyond what the plan's threat model already covers:
- T-02-03 (Information Disclosure via Tavily str(e)): mitigated — no `str(e)` in auth-error returns
- T-02-06 (BadRequestError handler): mitigated — returns query text (user-supplied), not str(e)

## Next Phase Readiness

- AGENT-01/02/03 complete and GREEN (8 tests)
- 48 of 51 tests passing; 3 remaining (QUAL-02/03/04) ready for Plan 03
- Plan 03 files: app/routers/chat.py (QUAL-02, QUAL-04) and app/auth.py (QUAL-03)

## Self-Check

- app/services/agent.py: verified modified (synthesis mandate + retry guards present)
- app/tools/web_search.py: verified modified (tavily.errors imports + try/except)
- Commit 4e688c6: feat(02-02): add synthesis mandate
- Commit 5ed1b3a: feat(02-02): add empty-completion retry
- Commit ca264ad: feat(02-02): wrap Tavily exceptions
- 48 passed, 3 failed (QUAL-02/03/04 — intentional, for Plan 03)

## Self-Check: PASSED

---
*Phase: 02-agent-reliability*
*Completed: 2026-05-03*
