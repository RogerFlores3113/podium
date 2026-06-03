"""Offline numpy-cosine ranker over frozen embeddings (EVAL-01, 20-02).

This is the deterministic core that runs in CI. It ranks corpus ids for a query
by *exact* cosine similarity over committed frozen vectors and scores those
rankings with the pure metrics from Plan 20-01. It imports ONLY numpy + stdlib +
``app.eval`` — no OpenAI, no DB, no app.services, no app.config. That isolation
is what lets the regression gate collect and run under a fake key with no
Postgres.

Exact cosine here intentionally approximates pgvector's ordering: the live
HNSW index is *approximate*, so the offline gate measures embedding+ranking
quality in isolation while the live runner (scripts/eval_retrieval.py) measures
the real index path. Determinism comes from L2-normalization and a stable
argsort, so tied similarities resolve in a fixed order.

frozen_vectors.json schema::

    {
      "embedding_model": str,
      "dimensions": int,
      "synthetic": bool,            # True => placeholder vectors, not real OpenAI
      "corpus": {id: [float, ...]},
      "queries": {query_text: [float, ...]},
      "baseline": {"mrr": float, "hit_rate_at_5": float}
    }
"""

import json
from pathlib import Path
from statistics import mean

import numpy as np

from app.eval.dataset import EvalCase
from app.eval.metrics import hit_rate_at_k, reciprocal_rank


def rank_by_cosine(
    query_vec: list[float],
    corpus_vecs: list[list[float]],
    corpus_ids: list[str],
) -> list[str]:
    """Rank corpus ids by exact cosine similarity to the query (best first).

    L2-normalizes the query and every corpus row with a 1e-12 guard against
    zero vectors, then sorts by descending similarity with a stable argsort so
    ties resolve deterministically. Returns a full permutation of corpus_ids.
    """
    q = np.asarray(query_vec, dtype=np.float64)
    matrix = np.asarray(corpus_vecs, dtype=np.float64)
    q_norm = q / (np.linalg.norm(q) + 1e-12)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12)
    sims = matrix_norm @ q_norm
    order = np.argsort(-sims, kind="stable")
    return [corpus_ids[i] for i in order]


def load_frozen(path: Path) -> dict:
    """Load frozen_vectors.json (corpus/query vectors + baseline + provenance)."""
    return json.loads(Path(path).read_text())


def rank_case(frozen: dict, case: EvalCase) -> list[str]:
    """Rank the frozen corpus ids for one golden case using its frozen query vector."""
    corpus_ids = list(frozen["corpus"])
    corpus_vecs = [frozen["corpus"][cid] for cid in corpus_ids]
    return rank_by_cosine(frozen["queries"][case.query], corpus_vecs, corpus_ids)


def evaluate(frozen: dict, golden: list[EvalCase]) -> dict[str, float]:
    """Rank every golden query over the frozen corpus and return mean metrics.

    Returns mean hit-rate@3, hit-rate@5, and MRR across all cases. MRR is the
    mean reciprocal rank; the metric functions themselves live in Plan 20-01.
    """
    rankings = [(rank_case(frozen, case), case.relevant_ids) for case in golden]
    return {
        "hit_rate_at_3": mean(hit_rate_at_k(r, rel, 3) for r, rel in rankings),
        "hit_rate_at_5": mean(hit_rate_at_k(r, rel, 5) for r, rel in rankings),
        "mrr": mean(reciprocal_rank(r, rel) for r, rel in rankings),
    }
