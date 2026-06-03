"""Stdlib JSON loaders for the retrieval-eval corpus and golden set (EVAL-01).

The corpus and golden labels are hand-authored fixtures under ``tests/eval/``.
Keeping these loaders dependency-free (stdlib ``json`` + ``dataclasses`` only —
no app.services, no app.config, no OpenAI, no DB) is what lets the offline CI
gate import them and run with a fake key and no Postgres.

The corpus is a list of ``{"id", "text"}`` objects with STABLE string ids, so
relevance labels never depend on the live chunker (RAG-01 boundary churn cannot
invalidate them). The golden set is a list of ``{"query", "relevant_ids"}``
objects, each labeled by human judgement of meaning — never by the embedder
(which would make the eval grade itself).
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvalCase:
    """One golden query and the set of corpus ids it should retrieve."""

    query: str
    relevant_ids: set[str]


def load_corpus(path: Path) -> dict[str, str]:
    """Load corpus.json into an ``id -> text`` mapping."""
    data = json.loads(Path(path).read_text())
    return {chunk["id"]: chunk["text"] for chunk in data}


def load_golden(path: Path) -> list[EvalCase]:
    """Load golden.json into a list of ``EvalCase`` (relevant_ids as sets)."""
    data = json.loads(Path(path).read_text())
    return [EvalCase(case["query"], set(case["relevant_ids"])) for case in data]
