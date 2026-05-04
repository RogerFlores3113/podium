---
phase: 03-destructive-ux-paths
plan: "01"
subsystem: tests
tags: [tdd, red-phase, conversations, memories, settings]
dependency_graph:
  requires: []
  provides:
    - tests/test_conversations.py
    - frontend/__tests__/SettingsPage.test.tsx
    - frontend/__tests__/ChatPage.test.tsx
  affects:
    - app/routers/chat.py (Wave 2 will add delete_conversation)
    - frontend/app/settings/page.tsx (Wave 2 will add memoryStatus + optimistic delete)
    - frontend/app/components/ChatPage.tsx (Wave 2 will add hoveredConvId + × button)
tech_stack:
  added: []
  patterns:
    - pytest asyncio unit-test with MagicMock AsyncSession (matches existing pattern)
    - vitest + @testing-library/react with vi.spyOn(globalThis, "fetch") mock chain
    - vi.useFakeTimers() for 3-second auto-clear lifecycle test
key_files:
  created:
    - tests/test_conversations.py
    - frontend/__tests__/SettingsPage.test.tsx
    - frontend/__tests__/ChatPage.test.tsx
  modified: []
decisions:
  - "Backend tests use direct function import + mocked AsyncSession (not httpx/AsyncClient) — matches established unit-test pattern in tests/ directory"
  - "ChatPage test mocks react-markdown and remark-gfm to avoid heavy render in jsdom"
  - "Added scrollIntoView stub in ChatPage test (jsdom limitation)"
  - "ChatPage test 1 (× button hidden) passes today and after Wave 2 — correct expected behavior"
metrics:
  duration: "~25 minutes"
  completed: "2026-05-03"
  tasks_completed: 3
  files_created: 3
---

# Phase 3 Plan 1: RED Tests for Destructive UX Paths Summary

Three new test files establishing the executable contract for Wave 2 (plans 03-02, 03-03).

## What Was Built

Three test files were written — 1 backend (pytest) and 2 frontend (vitest) — covering all behaviors Phase 3 introduces. The tests intentionally fail today because the production code does not yet exist.

### tests/test_conversations.py — CONV-01

Three async pytest tests for `DELETE /chat/{conversation_id}`:

1. `test_delete_conversation_happy_path` — verifies `db.delete(conv)` + `db.commit()` called, returns `{"detail": "Conversation deleted"}`
2. `test_delete_conversation_not_found_raises_404` — verifies HTTP 404 when SELECT returns None; delete/commit NOT called
3. `test_delete_conversation_other_user_returns_404` — verifies ownership guard via SQL WHERE filter; raises 404; delete/commit NOT called

**Failure mode:** `ImportError: cannot import name 'delete_conversation' from 'app.routers.chat'` (collection error, exit 2). This is the RED signal Wave 2 (03-02) resolves by adding the route.

### frontend/__tests__/SettingsPage.test.tsx — MEM-01 + MEM-02

Six vitest tests for SettingsPage UX improvements:

1. Optimistic memory delete — asserts row removed before slow DELETE resolves
2. Failure revert — asserts "Failed to delete memory" appears + row restored on 500
3. 3-second auto-clear — uses `vi.useFakeTimers()` to verify status message disappears
4. handleAddMemory success — asserts "Memory added" on 201
5. handleAddMemory failure — asserts "Failed to add memory" on 500
6. handleDeleteKey failure (D-09) — asserts "Failed to remove key" on 500

**Failure modes:** Tests 1-2 fail with AssertionError (element present when expected absent, or status text absent). Tests 3-6 fail with timeouts (waitFor never resolves because status state doesn't exist). All 6 fail, exit non-zero.

### frontend/__tests__/ChatPage.test.tsx — CONV-02

Six vitest tests for sidebar conversation delete:

1. × button hidden when row not hovered — **passes today** (correct: button absent = hidden)
2. × button appears on hover, disappears on unhover — fails (no `hoveredConvId` state)
3. Confirm cancel is no-op — fails (no × button to click)
4. Confirm OK → DELETE /chat/{id} → row removed — fails (no × button to click)
5. Active conversation delete → startNewConversation — fails (no × button)
6. × stopPropagation prevents loadConversation — fails (no × button)

**Failure modes:** `TestingLibraryElementError: Unable to find an element with the title: Delete conversation` for tests 2-6. Exit non-zero (5 failed). URL uses `/chat/{id}` (not `/conversations/{id}`) per research Pitfall 1 correction.

## Verification Results

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_conversations.py -v` | Exit 2 — ImportError RED |
| `cd frontend && npm test -- --run SettingsPage.test.tsx` | Exit 1 — 6 tests failed |
| `cd frontend && npm test -- --run ChatPage.test.tsx` | Exit 1 — 5 tests failed (1 passes correctly) |
| `uv run pytest tests/ --ignore=tests/test_conversations.py` | Exit 0 — 51 tests GREEN |
| `cd frontend && npm test -- --run --exclude="**/SettingsPage.test.tsx" --exclude="**/ChatPage.test.tsx"` | Exit 0 — 25 tests GREEN |

No regressions in existing test suite.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

### Notes

1. **`asyncio_mode = "auto"` in pyproject.toml** — The project already sets asyncio_mode=auto, making `@pytest.mark.asyncio` decorators optional. They were kept as required by the plan acceptance criteria.

2. **ChatPage Test 1 passes today** — Test 1 ("× button hidden when row is not hovered") correctly passes because the button simply doesn't exist in the DOM. This is expected: after Wave 2 adds the `hoveredConvId` hover state, the button will still be absent before hovering. The test verifies correct behavior in both RED and GREEN phases.

3. **SettingsPage timeout failures (Tests 3-6)** — Tests that call `waitFor(() => screen.getByText("Memory added"))` etc. time out at 5s because the status messages never appear (production code unchanged). This is valid RED — `waitFor` timeout is an assertion failure.

## Wave 2 Pointer

These tests become the green-bar contract for:
- **Plan 03-02** — implements `delete_conversation` route in `app/routers/chat.py` + ChatPage sidebar delete (turns `tests/test_conversations.py` and `frontend/__tests__/ChatPage.test.tsx` green)
- **Plan 03-03** — implements `memoryStatus`, optimistic delete, `handleDeleteKey` fix in `frontend/app/settings/page.tsx` (turns `frontend/__tests__/SettingsPage.test.tsx` green)

## Known Stubs

None — this plan creates test files only. No production stubs introduced.

## Threat Flags

None — test-only plan, no production code, no new network endpoints or trust boundaries.

## Self-Check

Files exist:
- tests/test_conversations.py: FOUND
- frontend/__tests__/SettingsPage.test.tsx: FOUND
- frontend/__tests__/ChatPage.test.tsx: FOUND

Commits exist:
- 4789288 test(03-01): add RED tests for DELETE /chat/{conversation_id}
- 4176e60 test(03-01): add RED tests for SettingsPage MEM-01 + MEM-02 + handleDeleteKey fix
- a637788 test(03-01): add RED tests for ChatPage sidebar delete CONV-02

## Self-Check: PASSED
