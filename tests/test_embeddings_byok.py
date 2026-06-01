"""Tests for BYOK embedding key forwarding and fallback (SEC-01, 19-03).

Embeddings use an OpenAI embedding model, so only a user's OpenAI BYOK key can
privatize embeddings. These tests pin the contract:
  - generate_embeddings forwards a provided api_key to aembedding.
  - generate_embeddings falls back to the system key when none is supplied.
  - call sites resolve the user's OpenAI key via get_user_api_key and forward it.
  - guests / users with no OpenAI key fall back to the system key.

asyncio_mode = auto, so async tests need no decorator.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings


def _fake_embedding_response(n: int = 1):
    """A litellm aembedding-shaped response: .data is a list of {"embedding": [...]}."""
    response = MagicMock()
    response.data = [{"embedding": [0.0] * 1536} for _ in range(n)]
    return response


async def test_generate_embeddings_forwards_provided_key():
    """generate_embeddings(texts, api_key="sk-user") forwards api_key="sk-user" to aembedding."""
    from app.services.ingestion import generate_embeddings

    with patch(
        "app.services.ingestion.aembedding", new_callable=AsyncMock
    ) as mock_aembedding:
        mock_aembedding.return_value = _fake_embedding_response(1)
        await generate_embeddings(["hello"], api_key="sk-user")

    assert mock_aembedding.call_args.kwargs["api_key"] == "sk-user", (
        "A provided api_key must be forwarded verbatim to aembedding"
    )


async def test_generate_embeddings_falls_back_to_system_key():
    """generate_embeddings(texts) with no api_key forwards settings.openai_api_key to aembedding."""
    from app.services.ingestion import generate_embeddings

    with patch(
        "app.services.ingestion.aembedding", new_callable=AsyncMock
    ) as mock_aembedding:
        mock_aembedding.return_value = _fake_embedding_response(1)
        await generate_embeddings(["hello"])

    assert mock_aembedding.call_args.kwargs["api_key"] == settings.openai_api_key, (
        "With no api_key, the system key (settings.openai_api_key) must be used"
    )


async def test_retrieve_relevant_chunks_resolves_user_key():
    """retrieve_relevant_chunks resolves the key via get_user_api_key and forwards it to generate_embeddings."""
    from app.services import retrieval

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    with patch(
        "app.services.retrieval.get_user_api_key", new_callable=AsyncMock
    ) as mock_resolve, patch(
        "app.services.retrieval.generate_embeddings", new_callable=AsyncMock
    ) as mock_embed:
        mock_resolve.return_value = "sk-user"
        mock_embed.return_value = [[0.0] * 1536]
        await retrieval.retrieve_relevant_chunks(db=db, query="q", user_id="u1")

    mock_resolve.assert_awaited_once_with(db, "u1", "openai")
    assert mock_embed.call_args.kwargs.get("api_key") == "sk-user", (
        "retrieve_relevant_chunks must forward the resolved user key to generate_embeddings"
    )


async def test_guest_no_key_falls_back_to_system():
    """When get_user_api_key returns None, generate_embeddings is called such that aembedding gets the system key."""
    from app.services import retrieval

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=[])))

    with patch(
        "app.services.retrieval.get_user_api_key", new_callable=AsyncMock
    ) as mock_resolve, patch(
        "app.services.ingestion.aembedding", new_callable=AsyncMock
    ) as mock_aembedding:
        mock_resolve.return_value = None
        mock_aembedding.return_value = _fake_embedding_response(1)
        await retrieval.retrieve_relevant_chunks(db=db, query="q", user_id="guest")

    assert mock_aembedding.call_args.kwargs["api_key"] == settings.openai_api_key, (
        "A guest / no-key user must fall back to the system key at the aembedding call"
    )
