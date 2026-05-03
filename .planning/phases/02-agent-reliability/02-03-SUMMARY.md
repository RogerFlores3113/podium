---
phase: 02-agent-reliability
plan: 03
subsystem: api
tags: [arq, deduplication, race-condition, sqlalchemy, IntegrityError, chat, auth]

dependency_graph:
  requires:
    - phase: 02-agent-reliability-plan-01
      provides: tests/test_agent_reliability.py (RED tests for QUAL-02, QUAL-03, QUAL-04)
  provides:
    - app/routers/chat.py: _job_id kwarg for arq job deduplication (QUAL-02)
    - app/routers/chat.py: history built before user_message flush (QUAL-04)
    - app/auth.py: IntegrityError catch + rollback + re-select in get_or_create_user (QUAL-03)
  affects: [04-loading-error-ux, 06-pr14-audit]

tech-stack:
  added: []
  patterns:
    - arq job deduplication via deterministic _job_id to prevent double-queuing
    - IntegrityError race-condition pattern for concurrent first-access user creation

key-files:
  created: []
  modified:
    - app/routers/chat.py
    - app/auth.py

key-decisions:
  - "Used _job_id=f'extract:{conversation.id}' for arq deduplication — conversation.id is server-generated UUID so cannot be guessed or manipulated by clients"
  - "Used scalar_one() (not scalar_one_or_none()) in the IntegrityError re-select — the user MUST exist at that point; a missing user would indicate a deeper bug, not a race"

patterns-established:
  - "arq deduplication: always pass _job_id with a deterministic key derived from the resource being processed"
  - "concurrent INSERT pattern: SELECT → INSERT (try) → except IntegrityError: rollback → re-SELECT"

requirements-completed: [QUAL-02, QUAL-03, QUAL-04]

duration: 6min
completed: 2026-05-03
---

# Phase 2 Plan 03: Agent Reliability GREEN Fixes (QUAL-02, QUAL-03, QUAL-04) Summary

**arq job deduplication via _job_id, get_or_create_user IntegrityError recovery, and history-before-flush reorder turn three QUAL requirements GREEN**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-05-03T22:20:00Z
- **Completed:** 2026-05-03T22:26:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `_job_id=f"extract:{conversation.id}"` to arq `enqueue_job` — rapid-fire messages for the same conversation no longer queue duplicate memory extractions (QUAL-02)
- Moved `build_conversation_history` call to before `user_message = Message(...)` flush — the current user message no longer appears twice in LLM context (QUAL-04)
- Wrapped User INSERT in `get_or_create_user` with `try/except IntegrityError` — concurrent first-access requests no longer produce unhandled 500s; the function returns the existing user instead (QUAL-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _job_id kwarg + reorder history before flush (QUAL-02, QUAL-04)** - `ba0b1e6` (feat)
2. **Task 2: IntegrityError catch in get_or_create_user (QUAL-03)** - `45947a5` (feat)

## Files Created/Modified

- `app/routers/chat.py` - Added `_job_id` kwarg to `enqueue_job`; moved `build_conversation_history` block before `user_message = Message()`
- `app/auth.py` - Added `from sqlalchemy.exc import IntegrityError` import; wrapped User INSERT in try/except with rollback + re-select

## Decisions Made

- Used `scalar_one()` (not `scalar_one_or_none()`) in the IntegrityError re-select path: the user must exist at that point since the IntegrityError proves a concurrent INSERT succeeded. Using `scalar_one()` lets any underlying data integrity issue surface rather than silently returning None.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None — no placeholder values, hardcoded empty data, or un-wired components.

## Threat Flags

None — changes are internal correctness fixes. No new network endpoints, auth paths, or trust boundary surface introduced.

## Self-Check: PASSED

- app/routers/chat.py: FOUND
- app/auth.py: FOUND
- Commit ba0b1e6: FOUND
- Commit 45947a5: FOUND
- test_memory_job_uses_job_id: PASSED
- test_history_excludes_current_message: PASSED
- test_get_or_create_user_race_condition: PASSED
- 40 pre-existing tests: all still PASSING

## Next Phase Readiness

- All 3 QUAL requirements from this plan are GREEN
- Plan 02 (AGENT-01, AGENT-02, AGENT-03) handles the remaining 8 Phase 2 tests
- Phase 2 complete when Plan 02 wave also merges

---
*Phase: 02-agent-reliability*
*Completed: 2026-05-03*
