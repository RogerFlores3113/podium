"""Unit tests for the pure retrieval metric functions (EVAL-01, 20-01).

These three functions are the scoring core of the retrieval-evaluation harness.
Both the offline CI gate (Plan 20-02) and the live runner reuse them unchanged,
so they must be provably correct in isolation over tiny hand-checked inputs.

The functions are pure (no I/O, no DB, no OpenAI), so these tests are plain sync
pytest functions with synthetic ranked lists and relevant-id sets — no fixtures,
no JSON, no numpy. asyncio_mode = auto, but nothing here is async.
"""

from app.eval.metrics import hit_rate_at_k, recall_at_k, reciprocal_rank


# --- hit_rate_at_k -----------------------------------------------------------


def test_hit_rate_is_one_when_a_relevant_id_is_in_top_k():
    assert hit_rate_at_k(["a", "b", "c"], {"b"}, k=2) == 1.0


def test_hit_rate_is_zero_when_no_relevant_id_is_in_top_k():
    assert hit_rate_at_k(["a", "b", "c"], {"z"}, k=2) == 0.0


def test_hit_rate_ignores_relevant_ids_ranked_below_k():
    # "c" is relevant but sits at rank 3, outside top-2.
    assert hit_rate_at_k(["a", "b", "c"], {"c"}, k=2) == 0.0


def test_hit_rate_handles_k_larger_than_the_ranked_list():
    assert hit_rate_at_k(["a", "b"], {"b"}, k=5) == 1.0


def test_hit_rate_is_zero_when_relevant_ids_is_empty():
    assert hit_rate_at_k(["a", "b", "c"], set(), k=2) == 0.0


# --- recall_at_k -------------------------------------------------------------


def test_recall_is_one_when_the_only_relevant_id_is_in_top_k():
    assert recall_at_k(["a", "b", "c"], {"b"}, k=2) == 1.0


def test_recall_counts_fraction_of_relevant_in_top_k():
    # Two relevant ids, only "b" is in top-2 -> 1/2.
    assert recall_at_k(["a", "b", "c"], {"b", "c"}, k=2) == 0.5


def test_recall_is_zero_when_relevant_ids_is_empty():
    assert recall_at_k(["a", "b", "c"], set(), k=2) == 0.0


def test_recall_at_k_equals_three_captures_more_than_at_two():
    ranked = ["a", "b", "c", "d"]
    relevant = {"b", "c"}
    assert recall_at_k(ranked, relevant, k=2) == 0.5
    assert recall_at_k(ranked, relevant, k=3) == 1.0


def test_recall_handles_k_larger_than_the_ranked_list():
    assert recall_at_k(["a", "b"], {"a", "b"}, k=5) == 1.0


# --- reciprocal_rank ---------------------------------------------------------


def test_reciprocal_rank_is_half_when_first_relevant_is_at_rank_two():
    assert reciprocal_rank(["x", "b"], {"b"}) == 0.5


def test_reciprocal_rank_is_one_when_first_relevant_is_at_rank_one():
    assert reciprocal_rank(["b", "x"], {"b"}) == 1.0


def test_reciprocal_rank_is_zero_when_no_relevant_id_is_present():
    assert reciprocal_rank(["x", "y"], {"b"}) == 0.0


def test_reciprocal_rank_uses_the_first_relevant_id_only():
    # Both "b" (rank 2) and "c" (rank 3) are relevant; score is 1/2, not 1/3.
    assert reciprocal_rank(["x", "b", "c"], {"b", "c"}) == 0.5


def test_reciprocal_rank_is_zero_when_relevant_ids_is_empty():
    assert reciprocal_rank(["a", "b", "c"], set()) == 0.0


# --- ties / robustness -------------------------------------------------------


def test_metrics_do_not_error_on_empty_ranked_list():
    assert hit_rate_at_k([], {"b"}, k=3) == 0.0
    assert recall_at_k([], {"b"}, k=3) == 0.0
    assert reciprocal_rank([], {"b"}) == 0.0


def test_metrics_handle_duplicate_ids_in_ranked_list_without_error():
    # A degenerate ranking with ties/duplicates must still return a defined value.
    assert hit_rate_at_k(["a", "a", "b"], {"b"}, k=3) == 1.0
    assert reciprocal_rank(["a", "a", "b"], {"b"}) == 1.0 / 3


# --- discrimination: the gate has teeth -------------------------------------


def test_a_reversed_ranking_scores_strictly_lower_than_the_correct_ranking():
    # The correct ranking puts the single relevant id at the top; reversing it
    # buries the relevant id, so every metric must score strictly lower. This
    # seeds the "gate-has-teeth" proof reused by the offline gate in Plan 20-02.
    relevant = {"d"}
    correct = ["d", "c", "b", "a"]
    reversed_ranking = ["a", "b", "c", "d"]

    assert reciprocal_rank(reversed_ranking, relevant) < reciprocal_rank(
        correct, relevant
    )
    assert hit_rate_at_k(reversed_ranking, relevant, k=2) < hit_rate_at_k(
        correct, relevant, k=2
    )
    assert recall_at_k(reversed_ranking, relevant, k=2) < recall_at_k(
        correct, relevant, k=2
    )
