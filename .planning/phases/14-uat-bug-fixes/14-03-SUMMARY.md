---
phase: 14-uat-bug-fixes
plan: 03
subsystem: agent
tags: [agent-loop, openai-responses-api, litellm, tool-calling, synthesis-fallback]

requires:
  - phase: prior-agent-work
    provides: "_run_responses_agent and run_agent loops with empty-completion guard and actor-critic"
provides:
  - "Consecutive tool-only iteration counter in both agent loops"
  - "Mid-loop synthesis nudge after 5 tool-only iterations"
  - "Forced synthesis LLM call after max-iteration exhaustion (tools=[] / tools=None)"
  - "Graceful fallback: error event only if forced synthesis itself produces empty text"
affects: [chat-streaming, guest-chat, web-search-flows]

tech-stack:
  added: []
  patterns:
    - "Nudge-then-force-synthesis pattern: counter increments only on tool-only iterations, resets when text appears, threshold-triggered nudge mid-loop, post-loop forced synthesis call without tools"

key-files:
  created: []
  modified:
    - app/services/agent.py

key-decisions:
  - "Threshold of 5 tool-only iterations chosen as half of agent_max_iterations (10) — gives the model enough room to gather context before being redirected"
  - "Forced synthesis emits the same streaming token / assistant_message / done event sequence as a normal final response so the frontend needs no changes"
  - "If forced synthesis itself produces empty text or raises, the original error event is preserved as the last-resort fallback"

patterns-established:
  - "Tool-only iteration tracking: increment counter when tool_calls present and accumulated_text is empty; reset otherwise"
  - "Forced synthesis post-loop: mirror the in-loop LLM call shape but disable tools (tools=[] for Responses API, tools=None for litellm)"

requirements-completed: [BUG-02]

duration: 8min
completed: 2026-05-06
---

# Phase 14 Plan 03: Forced Synthesis Fallback for Tool-Only Loops Summary

**Both agent loops (Responses API and litellm) now nudge the model toward synthesis after 5 consecutive tool-only iterations and force a tool-disabled synthesis call at max iterations before falling through to the error pill.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-06T23:07:00Z
- **Completed:** 2026-05-06T23:15:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `consecutive_tool_only_iterations` counter and threshold-5 nudge to `_run_responses_agent` (Responses API loop)
- Added the same counter + nudge to `run_agent`'s litellm loop
- Replaced the post-loop error yield in both loops with a forced synthesis attempt: `client.responses.create(tools=[])` and `acompletion(tools=None)`
- Forced synthesis streams tokens to the frontend and yields `assistant_message` + `done` only if text is produced; on empty/exception, falls through to the original error event
- All 109 existing tests still pass

## Task Commits

1. **Task 1: Add nudge counter + forced synthesis to _run_responses_agent (BUG-02, Loop 1)** - `c7fb8d8` (fix)
2. **Task 2: Add nudge counter + forced synthesis to run_agent litellm loop (BUG-02, Loop 2)** - `c0e49cd` (fix)

## Files Created/Modified
- `app/services/agent.py` - Added counter declarations, threshold-5 nudge blocks at end of each iteration body, and post-loop forced synthesis blocks (Responses API: `tools=[]`; litellm: `tools=None`)

## Decisions Made
- **Threshold = 5** (half of `agent_max_iterations = 10`): leaves room for legitimate multi-tool research while still catching runaway loops well before exhaustion.
- **Nudge content is identical across loops** (`"You have gathered enough information. Stop calling tools and write your final answer now."`) — easier to grep/audit and consistent for the model regardless of which API path it took.
- **Forced synthesis preserves the `assistant_message` + `done` event contract** so the chat persistence layer and frontend treat it as a normal final answer; the error event is only emitted if synthesis itself fails or produces no text.
- **`_effort_map` is redeclared inside the post-loop forced synthesis block in `_run_responses_agent`** because the in-loop declaration is scoped to the for-body. This is intentional and noted in the plan.

## Deviations from Plan

None - plan executed exactly as written. Both tasks applied verbatim with the exact code blocks specified in the plan; no Rule 1/2/3 deviations triggered, no auth gates encountered.

## Verification

- `python3 -c "import ast; ast.parse(open('app/services/agent.py').read()); print('OK')"` → OK
- `grep -c "consecutive_tool_only_iterations" app/services/agent.py` → 10 (well above the required 6: 2 declarations + 2 increments + 2 resets + 4 references in conditions/log messages)
- `grep -n "tools=\[\]" app/services/agent.py` → exactly 1 line (Responses API forced synthesis)
- `grep -n "tools=None" app/services/agent.py` → exactly 1 line (litellm forced synthesis)
- `grep -c "You have gathered enough information" app/services/agent.py` → 2 (one per loop)
- `grep -c "forced synthesis" app/services/agent.py` → 2 logger.warning calls
- `pytest tests/ -q` → 109 passed (run via `/home/rflor/podium/.venv/bin/python` since worktree has no module install)

## Issues Encountered

- The worktree filesystem has no Python venv of its own; running `python3 -m pytest` from the worktree fails on `ModuleNotFoundError: No module named 'litellm'`. Resolved by invoking the main repo's venv interpreter (`/home/rflor/podium/.venv/bin/python -m pytest tests/ -q`) which sees the same source tree via the worktree path. This is a pre-existing environment setup observation, not a code issue.

## Self-Check: PASSED

- `app/services/agent.py` modified — present in worktree (verified via grep counts above)
- Commit `c7fb8d8` (Task 1) — found in `git log` on `worktree-agent-a28f7652d76f5d82b`
- Commit `c0e49cd` (Task 2) — found in `git log` on `worktree-agent-a28f7652d76f5d82b`

## Next Phase Readiness

- BUG-02 fix is complete in both code paths. The chat endpoint and frontend require no changes — the forced synthesis call emits the same `token` / `assistant_message` / `done` event sequence that a normal final answer would.
- Recommend a follow-up smoke test in Phase 6 (PR #14 audit) to confirm a guest gpt-5-nano session that previously triggered 10 tool-only iterations now produces a synthesized answer rather than the pink error pill.

---
*Phase: 14-uat-bug-fixes*
*Plan: 03*
*Completed: 2026-05-06*
