"""Tests for memory_save tool (MEM-01, D-09-01)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_db():
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


def test_memory_save_is_registered_in_tool_schemas():
    """memory_save tool must appear in get_tool_schemas() (MEM-01)."""
    from app.tools import get_tool_schemas
    schemas = get_tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert "memory_save" in names, "memory_save must be registered in get_tool_schemas()"


def test_memory_save_not_in_guest_allowed_tools():
    """memory_save must be absent from GUEST_ALLOWED_TOOLS — guests cannot save memories (MEM-01, D-09-01)."""
    from app.services.agent import GUEST_ALLOWED_TOOLS
    assert "memory_save" not in GUEST_ALLOWED_TOOLS, (
        "memory_save must not be in GUEST_ALLOWED_TOOLS (blocked by omission, like python_executor)"
    )


@pytest.mark.asyncio
async def test_memory_save_calls_persist_memories_with_correct_args():
    """execute() calls persist_memories with the fact as content and normalized category (MEM-01)."""
    from app.tools.memory_save import MemorySaveTool
    from app.tools.base import ToolContext

    tool = MemorySaveTool()
    ctx = ToolContext(user_id="u1", db=_mock_db(), is_guest=False)

    with patch("app.tools.memory_save.persist_memories", new_callable=AsyncMock) as mock_persist:
        result = await tool.execute(ctx, {"fact": "User prefers bullet-point answers.", "category": "preference"})

    mock_persist.assert_awaited_once()
    call_kwargs = mock_persist.call_args
    memories_arg = call_kwargs.kwargs.get("memories") or call_kwargs.args[3]
    assert len(memories_arg) == 1
    assert memories_arg[0]["category"] == "preference"
    assert memories_arg[0]["content"] == "User prefers bullet-point answers."
    assert "Memory saved" in result


@pytest.mark.asyncio
async def test_memory_save_normalizes_invalid_category_to_context():
    """execute() with an unrecognized category must normalize to 'context' (MEM-01, Pitfall 4)."""
    from app.tools.memory_save import MemorySaveTool
    from app.tools.base import ToolContext

    tool = MemorySaveTool()
    ctx = ToolContext(user_id="u1", db=_mock_db(), is_guest=False)

    with patch("app.tools.memory_save.persist_memories", new_callable=AsyncMock) as mock_persist:
        await tool.execute(ctx, {"fact": "User works at Acme Corp.", "category": "personal"})

    call_kwargs = mock_persist.call_args
    memories_arg = call_kwargs.kwargs.get("memories") or call_kwargs.args[3]
    assert memories_arg[0]["category"] == "context", (
        "Unrecognized category 'personal' must be normalized to 'context'"
    )


# ---------------------------------------------------------------------------
# GAP: Dedup — persist_memories cosine similarity guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_memories_dedup_skips_duplicate_on_high_similarity():
    """Saving the same memory twice skips the second insert when similarity >= 0.95 (GAP dedup)."""
    from app.services.memory import persist_memories

    unit_vector = [1.0] + [0.0] * 1535  # 1536-dim unit vector

    # Fake row returned by dedup query: similarity above threshold
    fake_row = MagicMock()
    fake_row.similarity = 0.96

    fake_result = MagicMock()
    fake_result.fetchone.return_value = fake_row

    db = _mock_db()
    db.execute.return_value = fake_result

    with patch("app.services.memory.generate_embeddings", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [unit_vector]

        count = await persist_memories(
            db=db,
            user_id="u1",
            conversation_id=None,
            memories=[{"category": "preference", "content": "User prefers Python."}],
        )

    # Dedup should fire — db.add must NOT be called and count must be 0
    db.add.assert_not_called()
    assert count == 0, f"Expected 0 memories saved (duplicate skipped), got {count}"


@pytest.mark.asyncio
async def test_persist_memories_dedup_inserts_when_low_similarity():
    """Saving a semantically different memory still inserts when similarity < 0.95 (GAP dedup)."""
    from app.services.memory import persist_memories

    vector_a = [1.0] + [0.0] * 1535  # 1536-dim

    # Fake row with low similarity — should NOT trigger dedup
    fake_row = MagicMock()
    fake_row.similarity = 0.50

    fake_result = MagicMock()
    fake_result.fetchone.return_value = fake_row

    db = _mock_db()
    db.execute.return_value = fake_result

    with patch("app.services.memory.generate_embeddings", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [vector_a]

        count = await persist_memories(
            db=db,
            user_id="u1",
            conversation_id=None,
            memories=[{"category": "preference", "content": "User prefers JavaScript."}],
        )

    # Low similarity → should insert
    db.add.assert_called_once()
    assert count == 1, f"Expected 1 memory saved (different content), got {count}"
