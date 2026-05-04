---
phase: 02-agent-reliability
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - tests/test_agent_reliability.py
  - app/services/agent.py
  - app/tools/web_search.py
  - app/routers/chat.py
  - app/auth.py
findings:
  critical: 2
  warning: 5
  info: 2
  total: 9
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 2 implements agent reliability improvements: synthesis mandate in the system prompt (AGENT-01), empty-completion retry with nudge (AGENT-02), Tavily error sanitization (AGENT-03), arq job deduplication (QUAL-02), `get_or_create_user` race-condition handling (QUAL-03), and history-before-flush ordering (QUAL-04). The core logic is sound for most paths. However, two blockers were found: a silent test that never actually fails (making the rollback assertion vacuous), and a query-content echo in the `BadRequestError` handler that may reflect attacker-controlled input back to the LLM context. Five warnings cover double-commit risk, retry-only-on-iteration-0 asymmetry, an unused import, unvalidated `max_results`, and unsafe dict key access on Tavily results.

---

## Critical Issues

### CR-01: Rollback assertion is a no-op — QUAL-03 test always passes

**File:** `tests/test_agent_reliability.py:330`
**Issue:** Line 330 reads:
```python
db.rollback.assert_awaited_once(), "Must call rollback after IntegrityError"
```
The comma after `assert_awaited_once()` makes this a Python expression statement that builds a tuple `(None, "message string")` — it is NOT an `assert` statement. Tuples are always truthy, so Python never raises `AssertionError` here even when `rollback` was never called. The test for QUAL-03's most important postcondition is silently inert.

**Fix:**
```python
db.rollback.assert_awaited_once()  # raises AssertionError if not called
assert result is existing_user, "Must return the existing user found by re-select"
```

---

### CR-02: BadRequestError handler echoes unvalidated query into user-facing output

**File:** `app/tools/web_search.py:71`
**Issue:** When Tavily returns `BadRequestError`, the handler returns:
```python
return f"Web search failed for query: {query!r}. Please try rephrasing."
```
`query` is LLM-generated (derived from tool arguments passed by the model). If the model is manipulated into sending a crafted query string, that string is reflected verbatim into the tool result that is appended back to the LLM context and may be forwarded to the user. This is a prompt-injection vector — a malicious query value can smuggle text into the assistant turn or the SSE stream. All other error handlers in this file return static strings; this one is the exception and is inconsistent.

**Fix:**
```python
except BadRequestError:
    logger.warning("Tavily bad request for query %r", query, exc_info=True)
    return "Web search failed for that query. Please try rephrasing."
```

---

## Warnings

### WR-01: Double-commit risk — `done` and `error` events both commit, then `finally` commits again

**File:** `app/routers/chat.py:225,247,259`
**Issue:** `event_generator` commits on `done` (line 225), commits on `error` (line 247), and has a `finally` that always commits (line 259). When the agent ends normally (`done`), two commits fire: the `done` branch and `finally`. SQLAlchemy async sessions tolerate committing an already-committed transaction, but any exception raised between the first `commit()` and `finally` could leave the session in a bad state. More importantly, if an exception is raised inside the `finally` commit itself (e.g., a connection drop), the earlier commit's success masks it — the caller receives no error signal. The `error` branch also commits, which is unusual: an `error` event means the agent failed mid-turn; committing at that point persists a partial assistant-message sequence that may be internally inconsistent.

**Fix:** Remove the redundant intermediate `commit()` calls from the `done` and `error` branches and rely solely on the `finally` commit, which already runs unconditionally:
```python
elif event_type == "done":
    # memory extraction scheduling only — no commit here
    try:
        redis_pool = request.app.state.redis_pool
        await redis_pool.enqueue_job(...)
    except Exception as e:
        logger.warning(...)
    yield {"event": "done", "data": json.dumps(...)}
elif event_type == "error":
    yield {"event": "error", "data": json.dumps(...)}
# finally: await db.commit()  <-- single commit point
```

---

### WR-02: Empty-completion retry fires only on `iteration == 0`; subsequent tool-call iterations are unprotected

**File:** `app/services/agent.py:391-408` (litellm path) and `app/services/agent.py:183-199` (Responses API path)
**Issue:** The empty-completion guard retries with a nudge only when `iteration == 0`. If the model returns an empty completion on a later iteration (e.g., after a tool call), the agent falls through to "no tool calls → final response" and yields an empty `assistant_message` with no content. The frontend will display an empty assistant bubble. There is no fallback for this case.

**Fix:** Extend the fallback to any iteration where `accumulated_text` is empty after the stream ends and no tool calls were pending. The iteration-0 retry nudge is a reasonable special case, but the `else` branch (which yields the "wasn't able" message) should guard the final-response yield unconditionally:
```python
if not accumulated_tool_calls:
    if not accumulated_text.strip():
        # Whether this is a retry or not, don't yield an empty bubble
        yield {
            "type": "assistant_message",
            "content": "I wasn't able to generate a response. Please try again.",
            "tool_calls": None,
        }
    else:
        yield {"type": "assistant_message", "content": accumulated_text, "tool_calls": None}
    yield {"type": "done"}
    return
```

---

### WR-03: `lru_cache` imported but unused in `auth.py`

**File:** `app/auth.py:2`
**Issue:** `from functools import lru_cache` is imported at the top of `auth.py` but `lru_cache` is never used. The module uses a manual `global _jwks_client` singleton pattern instead. The unused import is dead code and mildly misleading (a reader might expect `lru_cache` to be applied somewhere).

**Fix:** Remove the unused import:
```python
# Remove this line:
from functools import lru_cache
```

---

### WR-04: `max_results` from tool arguments is not validated before being passed to Tavily

**File:** `app/tools/web_search.py:46,57`
**Issue:** `max_results = args.get("max_results", 5)` is passed directly to `client.search()` with no bounds check. The tool schema declares it as `1-10` in the description but does not enforce it. The LLM (or an adversarial prompt injection) could supply `max_results=1000`, causing a `BadRequestError` from Tavily at best, or an unexpectedly large result payload that exceeds token limits and degrades context quality.

**Fix:**
```python
max_results = max(1, min(int(args.get("max_results", 5)), 10))
```

---

### WR-05: Unsafe dict key access on Tavily result items — `KeyError` on malformed responses

**File:** `app/tools/web_search.py:86-88`
**Issue:** The result-formatting loop accesses `r['title']`, `r['url']`, and `r['content']` as bare dict lookups. If Tavily returns a result object missing any of these keys (e.g., an API change or partial result), the entire `execute()` method raises an unhandled `KeyError`, propagating as an unhandled exception to the agent (which will format it as `Error: 'title'` — confusing and unhelpful). The generic `except Exception` at line 73 does not cover this path because the KeyError occurs after the try/except block.

**Fix:**
```python
for i, r in enumerate(results, 1):
    title = r.get("title", "Untitled")
    url = r.get("url", "")
    content = r.get("content", "")[:800]
    formatted.append(f"{i}. {title}\n   URL: {url}\n   {content}")
```

---

## Info

### IN-01: System-prompt mentions `python_executor` but guests are silently denied it without prompt update

**File:** `app/services/agent.py:26,33,47-49`
**Issue:** `AGENT_SYSTEM_PROMPT` lists `python_executor` as an available tool and instructs the model to use it. However, `GUEST_ALLOWED_TOOLS` excludes `python_executor`, so when a guest session filters tool schemas, the tool is unavailable. The model will still attempt to call `python_executor` (because the system prompt says it's available), receive an `Error: Unknown tool 'python_executor'` response, and waste a tool-call round-trip. There is no guest-specific system prompt variant.

**Fix:** Either add a guest-specific system prompt that omits `python_executor`, or conditionally patch the system prompt when `is_guest=True` to remove the `python_executor` bullet points before the message list is built.

---

### IN-02: `_run_responses_agent` mutates the caller's `input_messages` list in-place

**File:** `app/services/agent.py:185-215`
**Issue:** `_run_responses_agent` appends to `input_messages` across iterations (lines 185, 203-215). This list is passed in from `run_agent` (line 314), which constructs it via `_to_responses_input(messages)`. Since `_to_responses_input` returns a new list, mutation does not affect the caller's `messages` variable — so there is no bug today. However, the function signature does not communicate that it mutates its argument. If `run_agent` is refactored to pass the list by reference from elsewhere, or if `_run_responses_agent` is reused in a different context, silent list mutation will cause hard-to-trace bugs.

**Fix:** Document the mutation contract in the function docstring, or accept the list and return an updated copy. At minimum, add a comment at the call site:
```python
# NOTE: _run_responses_agent mutates input_messages in-place across iterations
input_messages = _to_responses_input(messages)
```

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
