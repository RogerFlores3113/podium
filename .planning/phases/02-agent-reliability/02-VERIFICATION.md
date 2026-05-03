---
phase: 02-agent-reliability
verified: 2026-05-03T23:00:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Send a message that triggers web_search (e.g., 'What happened in the news today?') and observe the chat thread"
    expected: "A synthesized answer referencing search results appears — no empty assistant bubble"
    why_human: "End-to-end SSE streaming with a live Tavily query cannot be verified programmatically without a running server and real API keys"
  - test: "Trigger a Tavily auth failure (e.g., with an invalid TAVILY_API_KEY set) and send a web-search message"
    expected: "A user-safe error string appears in the chat with no API key or internal trace visible to the user"
    why_human: "Requires a running server with a deliberately invalid key to observe the sanitized string in the UI"
---

# Phase 2: Agent Reliability Verification Report

**Phase Goal:** After any tool call, the agent always synthesizes and returns a user-visible answer; transient empty completions retry once; tool errors are sanitized.
**Verified:** 2026-05-03T23:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | AGENT_SYSTEM_PROMPT contains an explicit synthesis mandate with "MUST" and "IMPORTANT" | VERIFIED | `app/services/agent.py` lines 39-44: "IMPORTANT — Tool synthesis rule: After EVERY tool call, you MUST write a complete response..." |
| 2 | litellm path retries once when accumulated_text is empty and accumulated_tool_calls is empty, on iteration == 0 | VERIFIED | `app/services/agent.py` lines 391-408: guard fires before `if not accumulated_tool_calls:` branch; `continue` advances iteration; fallback yields "I wasn't able to generate a response" on else |
| 3 | litellm path yields a fallback assistant_message string on second empty completion | VERIFIED | `app/services/agent.py` lines 401-408: `else` branch yields `{"type": "assistant_message", "content": "I wasn't able to generate a response. Please try again."}` |
| 4 | Responses API path retries once when accumulated_text is empty and pending_calls is empty, on iteration == 0 | VERIFIED | `app/services/agent.py` lines 182-200: `if not pending_calls: if not accumulated_text.strip(): if iteration == 0: ... continue` |
| 5 | web_search.py catches InvalidAPIKeyError, MissingAPIKeyError, ForbiddenError, UsageLimitExceededError, TavilyTimeoutError, BadRequestError, and Exception — all return user-safe strings with no API key in the return value | VERIFIED | `app/tools/web_search.py` lines 4-11 (imports from tavily.errors), lines 60-74 (5 specific handlers + catch-all; all return static strings; exc_info=True on all) |
| 6 | enqueue_job in chat.py passes _job_id=f'extract:{conversation.id}' as a kwarg | VERIFIED | `app/routers/chat.py` line 234: `_job_id=f"extract:{conversation.id}",` present before `_defer_by` kwarg |
| 7 | get_or_create_user in auth.py catches IntegrityError, calls rollback, and re-selects the existing user | VERIFIED | `app/auth.py` lines 110-122: `try/except IntegrityError: await db.rollback(); result = await db.execute(select(User)...); user = result.scalar_one()` |
| 8 | build_conversation_history is called BEFORE user_message = Message(...) in chat.py | VERIFIED | `app/routers/chat.py` lines 128-141: history block (line 128-132) precedes user_message creation (line 134) |

**Score:** 8/8 truths verified

### Deferred Items

None.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_agent_reliability.py` | 11 failing tests (RED baseline) for all 6 requirements | VERIFIED | File exists; 11 test functions confirmed via `grep -c "def test_"`; all 11 pass after implementation |
| `app/services/agent.py` | AGENT-01 synthesis mandate; AGENT-02 retry logic in both paths | VERIFIED | "IMPORTANT — Tool synthesis rule" at lines 39-44; retry guard at lines 391-408 (litellm) and 182-200 (Responses API) |
| `app/tools/web_search.py` | AGENT-03 Tavily exception handling with sanitized return strings | VERIFIED | Full try/except block at lines 53-74; 6 imports from tavily.errors; TavilyTimeoutError aliased correctly |
| `app/routers/chat.py` | QUAL-02 _job_id kwarg; QUAL-04 history-before-flush reorder | VERIFIED | `_job_id=f"extract:{conversation.id}"` at line 234; history block precedes user_message flush |
| `app/auth.py` | QUAL-03 IntegrityError catch + rollback + re-select | VERIFIED | `from sqlalchemy.exc import IntegrityError` at line 10; except block at lines 117-122 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/services/agent.py` | AGENT_SYSTEM_PROMPT constant | "IMPORTANT — Tool synthesis rule" string appended at end | VERIFIED | Lines 39-44 contain the full mandate block |
| `app/services/agent.py` litellm path | empty-completion guard | `not accumulated_tool_calls and not accumulated_text.strip()` before no-tool-call branch | VERIFIED | Line 391: exact pattern present |
| `app/services/agent.py` Responses API path | empty-completion guard | `not accumulated_text.strip()` inside `if not pending_calls:` block | VERIFIED | Lines 182-200: guard present with retry/fallback |
| `app/tools/web_search.py` | client.search() call | try/except wrapping AsyncTavilyClient init and search call | VERIFIED | Lines 53-74: entire client block wrapped; `except (InvalidAPIKeyError, MissingAPIKeyError, ForbiddenError)` at line 60 |
| `app/routers/chat.py` enqueue_job | arq Redis queue | `_job_id=f"extract:{conversation.id}"` prevents duplicate jobs | VERIFIED | Line 234: kwarg present |
| `app/auth.py` get_or_create_user | User table | IntegrityError catch + rollback + re-select | VERIFIED | Lines 117-122: full pattern implemented |
| `app/routers/chat.py` build_conversation_history | user_message = Message( | call ordering — history before flush | VERIFIED | history block at line 128-132 precedes user_message at line 134 |

### Data-Flow Trace (Level 4)

Not applicable — this phase modifies server-side agent logic and error handling, not components that render dynamic data from a data source. The artifacts are service/tool modules, not UI components.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 11 Phase 2 tests pass | `.venv/bin/pytest tests/test_agent_reliability.py -v` | 11 passed in 1.72s | PASS |
| Full 51-test suite passes (no regressions) | `.venv/bin/pytest tests/ -q` | 51 passed in 1.74s | PASS |
| AGENT_SYSTEM_PROMPT contains synthesis mandate | `grep "IMPORTANT" app/services/agent.py` | Line 39: "IMPORTANT — Tool synthesis rule:" | PASS |
| litellm empty-completion guard present | `grep "not accumulated_tool_calls and not accumulated_text.strip" app/services/agent.py` | Line 391: pattern found | PASS |
| Tavily errors imported from tavily.errors | `grep "from tavily.errors import" app/tools/web_search.py` | Line 4: import block found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| AGENT-01 | 02-02-PLAN.md | System prompt includes explicit synthesis rule after every tool result | SATISFIED | AGENT_SYSTEM_PROMPT lines 39-44; tests pass |
| AGENT-02 | 02-02-PLAN.md | Agent loop retries once on empty assistant text before yielding done (both paths) | SATISFIED | Retry guard in litellm path (lines 391-408) and Responses API path (lines 182-200); 3 tests pass |
| AGENT-03 | 02-02-PLAN.md | Tavily web search errors caught and sanitized, no key leakage | SATISFIED | try/except in web_search.py lines 53-74; exc_info=True on all handlers; 3 tests pass |
| QUAL-02 | 02-03-PLAN.md | Memory extraction job uses _job_id to prevent duplicate extractions | SATISFIED | `_job_id=f"extract:{conversation.id}"` at chat.py line 234; test passes |
| QUAL-03 | 02-03-PLAN.md | get_or_create_user race condition handled (IntegrityError catch + reload) | SATISFIED | try/except IntegrityError with rollback + re-select in auth.py lines 110-122; test passes |
| QUAL-04 | 02-03-PLAN.md | Conversation history excludes just-submitted user message (history built before flush) | SATISFIED | build_conversation_history called at line 128-132 before user_message = Message() at line 134; test passes |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/test_agent_reliability.py` | 330 | `db.rollback.assert_awaited_once(), "..."` — comma form means the custom message string is never displayed on failure (the assertion itself still works) | Info | No impact on test correctness — assertion fires correctly; only the custom message on failure is lost. The code reviewer (CR-01) incorrectly assessed this as a no-op. Confirmed: `assert_awaited_once()` is evaluated before the tuple is formed and will raise AssertionError if not awaited. |
| `app/tools/web_search.py` | 71 | `return f"Web search failed for query: {query!r}. Please try rephrasing."` — echoes LLM-generated query into tool result string | Warning | query is LLM-generated; a crafted prompt injection could smuggle text through the BadRequestError path into the assistant turn. All other handlers return static strings. This is the CR-02 finding from the code review — inconsistency is real but exploit requires a compromised LLM call, not a direct user action. |
| `app/tools/web_search.py` | 86-88 | `r['title']`, `r['url']`, `r['content']` accessed as bare dict lookups | Warning | If Tavily response is missing any key, an unhandled KeyError propagates outside the try/except block (WR-05 from code review). Does not affect phase goal achievement. |

### Human Verification Required

#### 1. End-to-end tool synthesis (SC-1)

**Test:** With the server running, send a chat message that triggers `web_search` — for example: "What are the top AI news stories today?" Observe the chat thread until completion.
**Expected:** A synthesized text response appears in the assistant bubble, referencing the web search results (with URLs cited). No empty assistant bubble is rendered at any point.
**Why human:** Requires a live server, Tavily API key, and real SSE streaming. Cannot verify end-to-end assistant synthesis behavior programmatically without a running application.

#### 2. Tavily error sanitization in UI (SC-3)

**Test:** Set `TAVILY_API_KEY` to an invalid value (e.g., `sk-invalid`), restart the server, send a message requiring web search.
**Expected:** The chat thread shows a user-safe error message (e.g., "Web search is temporarily unavailable.") with no API key, stack trace, or internal state visible in the UI.
**Why human:** Requires a running server with a deliberately broken Tavily key to observe the sanitized string rendered in the frontend.

### Gaps Summary

No gaps found. All 8 must-haves are VERIFIED against the actual codebase. The 51-test suite passes in full (40 pre-existing + 11 Phase 2 tests). Two warnings are flagged (BadRequestError query echo, bare dict access in web_search.py result formatting) but neither blocks the phase goal — they are quality items for a future cleanup.

Two human verification items remain for the two roadmap success criteria that require a running server and real external API behavior (SC-1 and SC-3). All programmatically verifiable evidence passes.

---

_Verified: 2026-05-03T23:00:00Z_
_Verifier: Claude (gsd-verifier)_
