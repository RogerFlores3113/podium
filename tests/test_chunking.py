"""Tests for boundary-aware chunk_text (RAG-01, 19-02).

These tests lock the boundary-aware chunking contract: chunks pack whole
sentences, never exceed chunk_size (except an oversize single sentence that
must be hard-split), carry whole-sentence overlap, and handle empty input.
"""

from app.services.ingestion import chunk_text


def test_empty_input_returns_an_empty_list():
    assert chunk_text("", 512, 50) == []


def test_whitespace_only_input_returns_an_empty_list():
    assert chunk_text("   \n\n  \t ", 512, 50) == []


def test_short_text_returns_a_single_stripped_chunk():
    text = "A short sentence. Another short one."
    result = chunk_text(text, 512, 50)
    assert result == [text.strip()]


def test_no_chunk_exceeds_size_for_normal_prose():
    # Five sentences, each well under chunk_size, total exceeds it.
    text = (
        "The quick brown fox jumps. "
        "The lazy dog sleeps soundly. "
        "Birds sing in the morning. "
        "Rivers flow toward the sea. "
        "Mountains stand against the sky."
    )
    chunks = chunk_text(text, 60, 10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 60, f"chunk exceeds size: {chunk!r}"


def test_chunks_do_not_cut_mid_sentence_for_normal_prose():
    text = (
        "The quick brown fox jumps. "
        "The lazy dog sleeps soundly. "
        "Birds sing in the morning. "
        "Rivers flow toward the sea. "
        "Mountains stand against the sky."
    )
    chunks = chunk_text(text, 60, 10)
    for chunk in chunks:
        # Every chunk of normal prose must end at a sentence terminator.
        assert chunk.rstrip()[-1] in ".!?", f"chunk cut mid-sentence: {chunk!r}"


def test_overlap_carries_a_whole_trailing_sentence_into_next_chunk():
    text = (
        "Sentence one is here. "
        "Sentence two is here. "
        "Sentence three is here. "
        "Sentence four is here."
    )
    chunks = chunk_text(text, 45, 22)
    assert len(chunks) > 1
    # The trailing sentence of chunk N must reappear at the start of chunk N+1.
    for first, second in zip(chunks, chunks[1:]):
        # Find a sentence in `first` that `second` starts with.
        carried = any(
            second.startswith(tail)
            for tail in _trailing_sentences(first)
        )
        assert carried, f"no whole-sentence overlap between {first!r} and {second!r}"


def test_oversize_single_sentence_is_hard_split():
    # One sentence, no internal sentence boundaries, longer than chunk_size.
    sentence = "word " * 40  # 200 chars, no terminator
    sentence = sentence.strip() + "."
    chunks = chunk_text(sentence, 50, 10)
    assert len(chunks) > 1, "oversize sentence must be hard-split into multiple chunks"
    # Pieces reconstruct the original sentence text (ignoring strip whitespace).
    reconstructed = "".join(chunks)
    assert reconstructed.replace(" ", "") == sentence.replace(" ", "")


def _trailing_sentences(chunk: str) -> list[str]:
    """Return progressively longer trailing-sentence suffixes of a chunk."""
    import re

    parts = re.findall(r"[^.!?]*[.!?]", chunk)
    parts = [p.strip() for p in parts if p.strip()]
    suffixes = []
    for i in range(len(parts)):
        suffixes.append(" ".join(parts[i:]))
    return suffixes
