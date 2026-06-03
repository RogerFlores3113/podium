"""Pure retrieval-quality metrics over ranked id lists (EVAL-01, 20-01).

These three functions are the entire scoring core of the retrieval-evaluation
harness. They are deliberately dependency-free — trivial list/set math with no
I/O, no DB, no OpenAI, and no numpy (numpy belongs to the offline ranker that
produces the rankings, not to the metrics that score them). Keeping them pure
lets both the offline CI gate (Plan 20-02) and the live runner reuse them
unchanged and unit-test them in isolation.

Each metric takes a ranked list of candidate ids (best first) and the set of
relevant ids for one query. MRR is intentionally not a function here: callers
compute ``statistics.mean(reciprocal_rank(...) for each query)``.
"""


def hit_rate_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Return 1.0 if any relevant id is in the top-k of the ranking, else 0.0.

    Answers "did we retrieve anything useful?" — the coarsest signal.
    """
    return 1.0 if relevant_ids & set(ranked_ids[:k]) else 0.0


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Return the fraction of relevant ids present in the top-k of the ranking.

    Answers "did we retrieve everything needed?" — matters when an answer needs
    multiple chunks. Returns 0.0 when there are no relevant ids (nothing to
    recall, and division by zero is undefined).
    """
    if not relevant_ids:
        return 0.0
    return len(relevant_ids & set(ranked_ids[:k])) / len(relevant_ids)


def reciprocal_rank(ranked_ids: list[str], relevant_ids: set[str]) -> float:
    """Return 1 / rank of the first relevant id (1-based), or 0.0 if none rank.

    Answers "is the best chunk near the top?" — matters because LLMs weight
    earlier context more heavily. The mean of this over all queries is MRR.
    """
    for rank, candidate_id in enumerate(ranked_ids, start=1):
        if candidate_id in relevant_ids:
            return 1.0 / rank
    return 0.0
