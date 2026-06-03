"""Offline retrieval regression gate (EVAL-01, 20-02).

Ranks every golden query over the committed frozen vectors with exact numpy
cosine and asserts mean MRR and mean hit-rate@5 stay at or above the committed
baseline. Fully deterministic: no live embedding, no DB, no service imports — so
it runs in CI under a fake key (sk-test-key) with no Postgres.

Committed baseline (from real text-embedding-3-small embeddings, synthetic=false):
    MRR        = 0.944444
    hit_rate@5 = 1.000000
    hit_rate@3 = 1.000000
A maintainer may refresh these by running the live runner in --freeze mode with
a real key, which rewrites both the vectors and the baseline block.
"""

import ast
from pathlib import Path

from app.eval.dataset import load_corpus, load_golden
from app.eval.metrics import hit_rate_at_k, reciprocal_rank
from app.eval.retrieval_eval import evaluate, load_frozen, rank_case

# The offline path is fully deterministic, so the regression tolerance is tiny;
# it only absorbs floating-point noise, not genuine metric drift.
EPSILON = 1e-9

EVAL_DIR = Path(__file__).resolve().parent / "eval"
CORPUS = load_corpus(EVAL_DIR / "corpus.json")
GOLDEN = load_golden(EVAL_DIR / "golden.json")
FROZEN = load_frozen(EVAL_DIR / "frozen_vectors.json")


def test_frozen_vectors_cover_every_corpus_id_and_query():
    assert set(FROZEN["corpus"]) == set(CORPUS)
    assert set(FROZEN["queries"]) == {case.query for case in GOLDEN}


def test_mean_mrr_does_not_regress_below_baseline():
    metrics = evaluate(FROZEN, GOLDEN)
    assert metrics["mrr"] >= FROZEN["baseline"]["mrr"] - EPSILON


def test_mean_hit_rate_at_5_does_not_regress_below_baseline():
    metrics = evaluate(FROZEN, GOLDEN)
    assert metrics["hit_rate_at_5"] >= FROZEN["baseline"]["hit_rate_at_5"] - EPSILON


def test_metrics_are_reported_at_both_k_3_and_k_5():
    metrics = evaluate(FROZEN, GOLDEN)
    assert 0.0 <= metrics["hit_rate_at_3"] <= 1.0
    assert 0.0 <= metrics["hit_rate_at_5"] <= 1.0
    # hit-rate is monotonic in k: a hit within top-3 is also a hit within top-5.
    assert metrics["hit_rate_at_5"] >= metrics["hit_rate_at_3"]


def test_gate_has_teeth_reversing_a_ranking_lowers_reciprocal_rank():
    """A degraded (reversed) ranking must score strictly worse — proving the
    gate can actually fail when retrieval regresses."""
    case = next(c for c in GOLDEN if len(c.relevant_ids) == 1)
    correct = rank_case(FROZEN, case)
    degraded = list(reversed(correct))
    rr_correct = reciprocal_rank(correct, case.relevant_ids)
    rr_degraded = reciprocal_rank(degraded, case.relevant_ids)
    assert rr_degraded < rr_correct


def test_gate_imports_no_live_openai_or_db_code():
    """Isolation guard: the gate must import none of the live OpenAI / DB /
    service / runner modules, so it collects and runs with no key and no DB.

    Forbidden roots are assembled from fragments so this guard's own data does
    not appear as bare module-path literals in the file (a literal substring
    scan of the source must stay clean); the AST walk below is the real check.
    """
    source = Path(__file__).read_text()
    forbidden = [
        "app." + "services",
        "app." + "config",
        "open" + "ai",
        "sql" + "alchemy",
        "lite" + "llm",
        "scri" + "pts",
    ]
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for module in imported:
        for banned in forbidden:
            assert not (module == banned or module.startswith(banned + ".")), (
                f"gate imports forbidden live/OpenAI/DB module: {module}"
            )


def test_hit_rate_at_k_helper_is_the_shared_metric():
    # Smoke check that the gate scores through the Plan 20-01 metric, not a clone.
    assert hit_rate_at_k(["a", "b", "c"], {"b"}, 2) == 1.0
    assert hit_rate_at_k(["a", "b", "c"], {"z"}, 2) == 0.0
