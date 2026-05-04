"""Tests for actor-critic self-critique pass (AGT-02, AGT-04, D-09-03, D-09-04)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


def _make_text_chunk(text: str):
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = text
    chunk.choices[0].delta.tool_calls = None
    return chunk


def _make_async_stream(chunks):
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


def _make_completion_response(text: str):
    """Simulate a non-streaming acompletion response for the critique call."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    return resp


@pytest.mark.asyncio
async def test_effort_fast_skips_actor_critic():
    """effort='fast' must not invoke the actor-critic acompletion call (AGT-04, D-09-03)."""
    from app.services.agent import run_agent

    text_stream = _make_async_stream([_make_text_chunk("My answer.")])
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.return_value = text_stream

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="Tell me about the job market.",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=False,
            effort="fast",
        ):
            events.append(event)

    # With effort=fast: only ONE acompletion call (the primary call), no critique call
    assert mock_acompletion.call_count == 1, (
        "effort='fast' must skip the actor-critic critique call — only 1 acompletion call expected"
    )
    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_events[-1]["content"] == "My answer."


@pytest.mark.asyncio
async def test_effort_balanced_triggers_actor_critic():
    """effort='balanced' must invoke the actor-critic acompletion call after the primary answer (AGT-02, AGT-04)."""
    from app.services.agent import run_agent

    text_stream = _make_async_stream([_make_text_chunk("My answer.")])
    critique_response = _make_completion_response("Revised answer with more detail.")
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = [text_stream, critique_response]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="Tell me about the job market.",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=False,
            effort="balanced",
        ):
            events.append(event)

    # With effort=balanced: TWO acompletion calls (primary + critique)
    assert mock_acompletion.call_count == 2, (
        "effort='balanced' must trigger actor-critic — 2 acompletion calls expected"
    )
    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_events[-1]["content"] == "Revised answer with more detail."


@pytest.mark.asyncio
async def test_lgtm_response_returns_original_text():
    """When critique responds with LGTM, the original answer is streamed unchanged (AGT-02, D-09-03)."""
    from app.services.agent import run_agent

    original = "This is a complete and accurate answer."
    text_stream = _make_async_stream([_make_text_chunk(original)])
    critique_response = _make_completion_response("LGTM — your answer is complete.")
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = [text_stream, critique_response]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="What are common recruiter questions?",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=False,
            effort="balanced",
        ):
            events.append(event)

    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_events[-1]["content"] == original, (
        "LGTM critique response must return the original answer unchanged"
    )


@pytest.mark.asyncio
async def test_non_lgtm_response_returns_revised_text():
    """When critique provides revised text (not LGTM), the revised text is streamed (AGT-02)."""
    from app.services.agent import run_agent

    text_stream = _make_async_stream([_make_text_chunk("Incomplete answer.")])
    revised = "Here is a much more complete and recruiter-focused answer."
    critique_response = _make_completion_response(revised)
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = [text_stream, critique_response]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="Explain salary benchmarking.",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=False,
            effort="balanced",
        ):
            events.append(event)

    assistant_events = [e for e in events if e["type"] == "assistant_message"]
    assert assistant_events[-1]["content"] == revised, (
        "Non-LGTM critique response must replace the original with the revised text"
    )


@pytest.mark.asyncio
async def test_guest_skips_actor_critic_regardless_of_effort():
    """Guest users always skip the actor-critic pass, even when effort='balanced' (AGT-04, D-09-03)."""
    from app.services.agent import run_agent

    text_stream = _make_async_stream([_make_text_chunk("Guest answer.")])
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.return_value = text_stream

        async for event in run_agent(
            db=db,
            user_id="guest-u1",
            user_message="Who are top companies hiring?",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=True,
            effort="balanced",
        ):
            events.append(event)

    # Guest with effort=balanced: still only 1 acompletion call (no critique)
    assert mock_acompletion.call_count == 1, (
        "Guest users must skip actor-critic — only 1 acompletion call expected even with effort='balanced'"
    )


@pytest.mark.asyncio
async def test_effort_thorough_triggers_actor_critic():
    """effort='thorough' must trigger actor-critic (same as balanced in Phase 9) (AGT-04, D-09-04)."""
    from app.services.agent import run_agent

    text_stream = _make_async_stream([_make_text_chunk("My thorough answer.")])
    critique_response = _make_completion_response("Revised thorough answer.")
    db = _mock_db()
    events = []

    with patch("app.services.agent.acompletion") as mock_acompletion:
        mock_acompletion.side_effect = [text_stream, critique_response]

        async for event in run_agent(
            db=db,
            user_id="u1",
            user_message="Analyze the engineering talent market.",
            conversation_history=[],
            api_key="sk-test",
            model="gpt-4o",
            is_guest=False,
            effort="thorough",
        ):
            events.append(event)

    assert mock_acompletion.call_count == 2, (
        "effort='thorough' must trigger actor-critic — 2 acompletion calls expected"
    )
