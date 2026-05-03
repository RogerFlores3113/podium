"""Tests for Phase 2 agent reliability fixes.

Covers: AGENT-01 (synthesis mandate), AGENT-02 (empty-completion retry),
AGENT-03 (Tavily error sanitization), QUAL-02 (arq job deduplication),
QUAL-03 (get_or_create_user race condition), QUAL-04 (history deduplication).
"""

import inspect
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from sqlalchemy.exc import IntegrityError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_empty_chunk():
    """Chunk with no text content and no tool calls — simulates empty completion."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = None
    chunk.choices[0].delta.tool_calls = None
    return chunk


def _make_text_chunk(text: str):
    """Chunk with text content and no tool calls."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = text
    chunk.choices[0].delta.tool_calls = None
    return chunk


def _make_async_stream(chunks):
    """Async iterable that yields the given chunks."""
    async def _aiter():
        for c in chunks:
            yield c
    mock = MagicMock()
    mock.__aiter__ = lambda self: _aiter()
    return mock


def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# AGENT-01: System prompt synthesis mandate
# ---------------------------------------------------------------------------

def test_system_prompt_contains_synthesis_rule():
    """AGENT_SYSTEM_PROMPT must contain an explicit synthesis mandate (AGENT-01)."""
    from app.services.agent import AGENT_SYSTEM_PROMPT
    assert "IMPORTANT" in AGENT_SYSTEM_PROMPT, (
        "AGENT_SYSTEM_PROMPT must contain an 'IMPORTANT' synthesis rule block"
    )
    assert "tool synthesis rule" in AGENT_SYSTEM_PROMPT.lower() or "tool synthesis" in AGENT_SYSTEM_PROMPT.lower(), (
        "AGENT_SYSTEM_PROMPT must contain a 'tool synthesis rule' instruction"
    )


def test_system_prompt_uses_imperative_must():
    """AGENT_SYSTEM_PROMPT must use 'MUST' language to mandate synthesis (AGENT-01)."""
    from app.services.agent import AGENT_SYSTEM_PROMPT
    assert "MUST" in AGENT_SYSTEM_PROMPT, (
        "AGENT_SYSTEM_PROMPT must use imperative 'MUST' language for the synthesis rule"
    )


# ---------------------------------------------------------------------------
# QUAL-02: arq job deduplication via _job_id
# ---------------------------------------------------------------------------

def test_memory_job_uses_job_id():
    """enqueue_job for memory extraction must pass _job_id=f'extract:{conversation.id}' (QUAL-02)."""
    import app.routers.chat as chat_module
    source = inspect.getsource(chat_module)
    assert '_job_id=f"extract:{conversation.id}"' in source or "_job_id=f'extract:{conversation.id}'" in source, (
        "enqueue_job must pass _job_id=f'extract:{conversation.id}' to deduplicate rapid-fire memory jobs"
    )


# ---------------------------------------------------------------------------
# AGENT-02: Empty-completion retry (litellm path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_litellm_empty_completion_retries():
    """On empty text + no tool calls at iteration 0, litellm path retries with a nudge (AGENT-02)."""
    from app.services.agent import run_agent

    empty_stream = _make_async_stream([_make_empty_chunk()])
    text_stream = _make_async_stream([_make_text_chunk("Here is my answer.")])

    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        # First call returns empty, second returns text
        mock_acompletion.side_effect = [empty_stream, text_stream]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="What is the news?",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",  # non-Responses-API model
        ):
            events.append(event)

    event_types = [e["type"] for e in events]
    # Must retry — acompletion called twice
    assert mock_acompletion.call_count == 2, (
        "Agent must call acompletion twice: once for empty response, once after nudge"
    )
    assert "done" in event_types, "Agent must eventually yield done"
    # The final assistant message must contain real text
    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert any(e.get("content", "").strip() for e in assistant_events), (
        "Agent must yield a non-empty assistant_message after retry"
    )


@pytest.mark.asyncio
async def test_empty_completion_fallback_on_second_attempt():
    """On second empty completion, agent yields a fallback string instead of empty bubble (AGENT-02)."""
    from app.services.agent import run_agent

    empty_stream_1 = _make_async_stream([_make_empty_chunk()])
    empty_stream_2 = _make_async_stream([_make_empty_chunk()])

    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = [empty_stream_1, empty_stream_2]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="What is the news?",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
        ):
            events.append(event)

    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_events, "Must yield an assistant_message even on double-empty"
    last_content = assistant_events[-1].get("content", "")
    assert last_content.strip(), "Fallback assistant_message must have non-empty content"
    assert "wasn't able" in last_content.lower() or "try again" in last_content.lower(), (
        "Fallback message must indicate the agent couldn't generate a response"
    )


# ---------------------------------------------------------------------------
# AGENT-02: Empty-completion retry (Responses API path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_responses_api_empty_completion_retries():
    """On empty text + no pending tool calls at iteration 0, Responses API path retries (AGENT-02)."""
    from app.services.agent import run_agent

    # For gpt-5-nano (Responses API path), we need to mock the OpenAI client
    db = _mock_db()
    events = []

    # Simulate two response streams: first empty, second with text
    empty_event = MagicMock()
    empty_event.type = "response.output_text.delta"
    empty_event.delta = ""

    done_event = MagicMock()
    done_event.type = "response.completed"

    text_event = MagicMock()
    text_event.type = "response.output_text.delta"
    text_event.delta = "Here is my answer."

    async def _empty_stream():
        yield empty_event

    async def _text_stream():
        yield text_event

    mock_empty_response = MagicMock()
    mock_empty_response.__aiter__ = lambda self: _empty_stream()
    mock_text_response = MagicMock()
    mock_text_response.__aiter__ = lambda self: _text_stream()

    with patch("app.services.agent.AsyncOpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.responses.create = AsyncMock(
            side_effect=[mock_empty_response, mock_text_response]
        )

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="What is the news?",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-5-nano",  # Responses API model
        ):
            events.append(event)

    assert mock_client.responses.create.call_count == 2, (
        "Responses API path must call create twice on empty first response"
    )
    assert any(e["type"] == "done" for e in events), "Must yield done"


# ---------------------------------------------------------------------------
# AGENT-03: Tavily error sanitization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_web_search_invalid_key_sanitized():
    """InvalidAPIKeyError from Tavily returns a user-safe string with no key leaked (AGENT-03)."""
    from app.tools.web_search import WebSearchTool
    from tavily.errors import InvalidAPIKeyError
    from app.tools.base import ToolContext

    tool = WebSearchTool()
    ctx = ToolContext(user_id="u1", db=_mock_db(), is_guest=False)

    with patch("app.tools.web_search.AsyncTavilyClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.search = AsyncMock(side_effect=InvalidAPIKeyError("Your API key sk-tvly-SECRET is invalid"))

        with patch("app.tools.web_search.settings") as mock_settings:
            mock_settings.tavily_api_key = "sk-tvly-SECRET"
            result = await tool.execute(ctx, {"query": "test query"})

    assert "sk-tvly-SECRET" not in result, "API key must not appear in user-facing result"
    assert "unavailable" in result.lower() or "error" in result.lower(), (
        "Result must be a user-safe error string"
    )


@pytest.mark.asyncio
async def test_web_search_usage_limit_sanitized():
    """UsageLimitExceededError returns a user-safe string (AGENT-03)."""
    from app.tools.web_search import WebSearchTool
    from tavily.errors import UsageLimitExceededError
    from app.tools.base import ToolContext

    tool = WebSearchTool()
    ctx = ToolContext(user_id="u1", db=_mock_db(), is_guest=False)

    with patch("app.tools.web_search.AsyncTavilyClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.search = AsyncMock(side_effect=UsageLimitExceededError("quota exceeded"))

        with patch("app.tools.web_search.settings") as mock_settings:
            mock_settings.tavily_api_key = "sk-tvly-SECRET"
            result = await tool.execute(ctx, {"query": "test query"})

    assert "sk-tvly-SECRET" not in result, "API key must not appear in result"
    assert result.strip(), "Result must be non-empty"


@pytest.mark.asyncio
async def test_web_search_timeout_sanitized():
    """TavilyTimeoutError returns a user-safe string (AGENT-03)."""
    from app.tools.web_search import WebSearchTool
    from tavily.errors import TimeoutError as TavilyTimeoutError
    from app.tools.base import ToolContext

    tool = WebSearchTool()
    ctx = ToolContext(user_id="u1", db=_mock_db(), is_guest=False)

    with patch("app.tools.web_search.AsyncTavilyClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.search = AsyncMock(side_effect=TavilyTimeoutError("timed out"))

        with patch("app.tools.web_search.settings") as mock_settings:
            mock_settings.tavily_api_key = "sk-tvly-SECRET"
            result = await tool.execute(ctx, {"query": "test query"})

    assert "sk-tvly-SECRET" not in result, "API key must not appear in result"
    assert "timed out" in result.lower() or "try again" in result.lower() or "unavailable" in result.lower(), (
        "Timeout result must be a user-safe string"
    )


# ---------------------------------------------------------------------------
# QUAL-03: get_or_create_user race condition
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_or_create_user_race_condition():
    """IntegrityError on concurrent user creation is caught and resolved by re-select (QUAL-03)."""
    from app.auth import get_or_create_user
    from app.models import User

    existing_user = MagicMock(spec=User)
    existing_user.clerk_id = "user_abc"

    db = _mock_db()
    # First execute: SELECT returns None (user not found)
    # commit: raises IntegrityError (concurrent insert)
    # After rollback, second execute: SELECT returns existing_user
    first_select_result = MagicMock()
    first_select_result.scalar_one_or_none.return_value = None
    second_select_result = MagicMock()
    second_select_result.scalar_one.return_value = existing_user

    db.execute.side_effect = [first_select_result, second_select_result]
    db.commit.side_effect = IntegrityError("UNIQUE violation", None, None)

    result = await get_or_create_user.__wrapped__("user_abc", db) if hasattr(get_or_create_user, "__wrapped__") else await get_or_create_user("user_abc", db)

    db.rollback.assert_awaited_once(), "Must call rollback after IntegrityError"
    assert result is existing_user, "Must return the existing user found by re-select"


# ---------------------------------------------------------------------------
# QUAL-04: History deduplication — build before flush
# ---------------------------------------------------------------------------

def test_history_excludes_current_message():
    """build_conversation_history must be called BEFORE the user message flush in chat.py (QUAL-04)."""
    import app.routers.chat as chat_module
    source = inspect.getsource(chat_module)

    # Find positions of the key operations in source
    history_call_pos = source.find("build_conversation_history(")
    flush_after_user_msg_pos = source.find("await db.flush()")

    assert history_call_pos != -1, "build_conversation_history must be called in chat.py"
    assert flush_after_user_msg_pos != -1, "db.flush() must be called in chat.py"

    # history call must come BEFORE the first db.flush() that follows user_message creation
    # Specifically: the section 'user_message = Message(' must come AFTER history is built
    user_msg_create_pos = source.find("user_message = Message(")
    assert user_msg_create_pos != -1, "user_message = Message(...) must exist in chat.py"

    assert history_call_pos < user_msg_create_pos, (
        "build_conversation_history must be called BEFORE user_message = Message(...) "
        "to prevent the current message from appearing twice in LLM context (QUAL-04)"
    )
