---
phase: 11-refactor-test-audit
plan: "02"
subsystem: backend
tags: [refactor, actor-critic, dead-code, test-isolation]
dependency_graph:
  requires: []
  provides: [app/services/critic.py]
  affects: [app/services/agent.py, app/services/llm.py, tests/test_actor_critic.py]
tech_stack:
  added: []
  patterns: [module-extraction, single-responsibility]
key_files:
  created:
    - app/services/critic.py
  modified:
    - app/services/agent.py
    - app/services/llm.py
    - tests/test_actor_critic.py
decisions:
  - "Restructured test_actor_critic.py to use two separate patches (agent.acompletion for primary call, critic.acompletion for critic call) instead of a single shared mock — more precise after module extraction"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-05"
  tasks_completed: 4
  files_changed: 4
---

# Phase 11 Plan 02: Extract critic.py and clean llm.py Summary

Actor-critic function extracted from agent.py into standalone critic.py; dead code (SYSTEM_PROMPT, build_context_string, acompletion import) removed from llm.py; test patch targets updated to match new module boundary.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create app/services/critic.py | b433480 | app/services/critic.py (created) |
| 2 | Slim agent.py — import from critic | 9e4c21d | app/services/agent.py |
| 3 | Remove dead code from llm.py, update test patches | 0246654 | app/services/llm.py, tests/test_actor_critic.py |
| 4 | Verify full backend suite (GREEN gate) | — | (verification only, no new files) |

## What Was Built

**critic.py** — New stateless module owning the actor-critic self-critique pass. Exports `_actor_critic` (async function) and `RESPONSES_API_MODELS` (frozenset). No dependency on agent.py — no circular import risk.

**agent.py** — Slimmed by 49 lines. Imports `_actor_critic` and `RESPONSES_API_MODELS` from critic.py. The `from litellm import acompletion` import was kept (used in the main streaming loop).

**llm.py** — Three dead symbols removed:
- `from litellm import acompletion` (unused after build_context_string was deleted in a prior phase)
- `SYSTEM_PROMPT` constant (unused; agent.py has AGENT_SYSTEM_PROMPT)
- `build_context_string` function (unused dead code)

**test_actor_critic.py** — All 6 tests restructured to use two separate patches: `app.services.agent.acompletion` for the primary streaming call, `app.services.critic.acompletion` for the critic call. Tests for fast/guest modes assert `mock_critic.call_count == 0` explicitly.

## Test Results

- 106 backend tests passed, 0 failed
- test_actor_critic.py: 6/6 passed
- test_llm_utils.py: 6/6 passed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test patch restructure needed after module extraction**
- **Found during:** Task 3
- **Issue:** The plan said "replace all 6 `app.services.agent.acompletion` occurrences with `app.services.critic.acompletion`". After extraction, the primary streaming call remains in agent.py's namespace while the critic call is in critic.py's namespace. A naive single-patch swap would leave the primary acompletion call unmocked, causing real network calls in tests.
- **Fix:** Restructured each test to use two separate patches. Tests that skip the critic (fast/guest) assert `mock_critic.call_count == 0`. Tests that trigger the critic assert `mock_primary.call_count == 1` and `mock_critic.call_count == 1`. The plan's acceptance criterion of 6 `app.services.critic.acompletion` occurrences is satisfied.
- **Files modified:** tests/test_actor_critic.py
- **Commit:** 0246654

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- app/services/critic.py exists: FOUND
- app/services/agent.py modified (no _actor_critic body): VERIFIED
- app/services/llm.py cleaned (no acompletion/SYSTEM_PROMPT/build_context_string): VERIFIED
- tests/test_actor_critic.py has 6 occurrences of app.services.critic.acompletion: VERIFIED
- Commits b433480, 9e4c21d, 0246654: FOUND in git log
- 106 tests passed: VERIFIED
