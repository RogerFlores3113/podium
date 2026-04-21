# TODOS

Work captured but deferred. Each item has enough context to pick up in any future session.

---

## v7: Conversation Sidebar (HIGH PRIORITY)

**What:** `GET /conversations/` endpoint + sidebar UI. Users can navigate back to prior conversations.

**Why:** Chat history is what separates a toy from a daily driver. Currently all conversation state is in-memory — a page refresh loses everything.

**Pros:** Dramatically improves retention for friends/family users. Shows production thinking to recruiters (persistence, pagination).

**Cons:** Sidebar adds layout complexity. Mobile UX needs care (collapsed by default).

**Context:** Backend already has `GET /chat/{conversation_id}` which loads a conversation with messages. What's missing:
- `GET /conversations/` endpoint returning paginated list per user (title, created_at, id)
- Frontend sidebar component in `ChatPage.tsx`
- On select: set conversationId + fetch messages via existing endpoint

**Depends on:** v6 landing-chat-ux branch (which extracts ChatPage.tsx).

---

## v7: Model Capability Flags

**What:** Replace the hardcoded `model.startswith("ollama/")` tool-call disable with a capability map in config.

**Why:** Newer Ollama models (llama3.3:70b) support function calling reliably. The current check will disable tools on capable models.

**Pros:** Config change to enable tools on a new model, no code change needed.

**Cons:** Minor. The string-prefix check works fine for v6 target models.

**Context:** The check lives in `app/services/agent.py`, in the `acompletion()` call:
```python
tools=tool_schemas if not model.startswith("ollama/") else None,
```
Replace with a `MODEL_CAPABILITIES` dict in `config.py`:
```python
MODEL_CAPABILITIES = {
    "ollama/llama3.2": {"tools": False},
    "ollama/mistral":  {"tools": False},
    "ollama/llama3.3:70b": {"tools": True},
    # default: True
}
```

**Depends on:** v6 multi-model branch.

---

## v7: Frontend Unit Tests (vitest)

**What:** Install vitest + @testing-library/react. Add unit tests for frontend helpers and hooks.

**Why:** `tryParseImage()`, `useAuthFetch()`, and message rendering logic are untested. These are the most likely spots for subtle bugs.

**Pros:** Catches regressions in shared utilities before they break the chat.

**Cons:** vitest setup adds a dev dependency and a test script. Low friction with CC.

**Context:** Backend pytest is included in v6. Frontend tests deferred to keep v6 scope clean.
Priority tests:
- `tryParseImage('{"type":"image","url":"..."}')` → returns object
- `tryParseImage("regular text")` → returns null
- `useAuthFetch` attaches Authorization header
- Message bubble renders markdown (not raw text)

**Depends on:** v6 landing-chat-ux branch (which creates the components being tested).
