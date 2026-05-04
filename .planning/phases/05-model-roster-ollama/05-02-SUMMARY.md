---
phase: 05-model-roster-ollama
plan: "02"
subsystem: backend
tags: [model-roster, ollama, config, agent, chat-router]
dependency_graph:
  requires: []
  provides: [MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05]
  affects: [app/config.py, app/services/agent.py, app/routers/chat.py]
tech_stack:
  added: []
  patterns: [settings-filter, model-validation, api-base-injection]
key_files:
  created: []
  modified:
    - app/config.py
    - app/services/agent.py
    - app/routers/chat.py
    - tests/test_config.py
    - tests/test_agent.py
decisions:
  - "claude-haiku-4-5 used as alias ID per D-01 locked decision; dated form deferred to Phase 6 audit"
  - "Tests added in plan 05-02 since plan 05-01 RED stubs were absent from worktree"
metrics:
  duration: "~15 minutes"
  completed: "2026-05-03"
---

# Phase 05 Plan 02: Model Roster GREEN Implementation Summary

## One-liner

Updated AVAILABLE_MODELS to 7 approved entries with middle-dot labels, added ollama_base_url to Settings, wired Ollama api_base + None-chunk guard in agent.py, and added list_models() filtering + 422 model validation in chat.py.

## What Was Built

### Task 1 — app/config.py
- `AVAILABLE_MODELS` rewritten: 4 core models (gpt-5-nano, gpt-5.4-nano, claude-sonnet-4-6, claude-haiku-4-5) + 3 Ollama entries
- All non-Ollama labels include middle-dot (·) separator
- Legacy entries removed: gpt-4o-mini, gpt-4o, claude-3-5-haiku-20241022, claude-3-5-sonnet-20241022
- `Settings.ollama_base_url: str = ""` added before model_config

### Task 2 — app/services/agent.py
- `RESPONSES_API_MODELS` updated to `frozenset({"gpt-5-nano", "gpt-5.4-nano"})`
- `api_base` injected into `acompletion()` call when `resolved_model.startswith("ollama/")`
- `if chunk is None: break` guard added as first statement inside `async for chunk in response:` loop

### Task 3 — app/routers/chat.py
- `list_models()` now filters out `provider == "ollama"` entries when `settings.ollama_base_url` is falsy
- Stream endpoint validates `body.model` against `await list_models()` output, raises `HTTPException(422)` for unknown models

### Tests Added
7 new GREEN tests in test_config.py and test_agent.py covering MODEL-01 through MODEL-05 requirements.

## Deviations from Plan

### Auto-added Missing Tests

**[Rule 2 - Missing Critical Functionality] Added plan 05-01 RED tests inline**
- **Found during:** Pre-task verification — worktree test files lacked the 6 failing stubs that plan 05-01 was supposed to create
- **Fix:** Added all required tests directly in plan 05-02 as GREEN tests (implementation already correct)
- **Files modified:** tests/test_config.py, tests/test_agent.py
- **Commit:** 7bcc899

## Test Results

All 22 tests pass in test_config.py + test_agent.py. Full suite (33 tests) all GREEN.

```
22 passed in 1.68s
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 (config.py) | bd083bb | feat(05-02): update AVAILABLE_MODELS roster and add ollama_base_url setting |
| Task 2 (agent.py) | a043cc6 | feat(05-02): add gpt-5.4-nano to RESPONSES_API_MODELS, None-chunk guard, Ollama api_base |
| Task 3 (chat.py) | 68fdb11 | feat(05-02): filter list_models() by ollama_base_url and validate model on stream endpoint |
| Tests | 7bcc899 | test(05-02): add GREEN tests for MODEL-01 through MODEL-05 roster requirements |

## Self-Check: PASSED

- app/config.py: FOUND, contains claude-sonnet-4-6, ollama_base_url
- app/services/agent.py: FOUND, contains gpt-5.4-nano, if chunk is None, ollama_base_url
- app/routers/chat.py: FOUND, contains ollama_base_url filter, Model not available 422
- All commits verified in git log
