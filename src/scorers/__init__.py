"""Scorers. Every scorer takes the FINAL ANSWER only (thinking already removed)
and returns a dict with at least `correct` (bool, or None when it cannot be
decided here) plus what it extracted, so a wrong score can be audited.

`judge_pairwise` is not in this registry: it needs a second model and runs as
its own step (see judge.py).
"""

from .answers import score_exact_match, score_grid_match, score_math_verify, score_mcq
from .code_exec import score_code_exec
from .ifeval import score_ifeval

SCORERS = {
    "math_verify": score_math_verify,
    "mcq": score_mcq,
    "exact_match": score_exact_match,
    "grid_match": score_grid_match,
    "code_exec": score_code_exec,
    "ifeval": score_ifeval,
}


def score(item: dict, answer: str) -> dict:
    """Score one final answer against one item (a row of data/{benchmark}/{lang}.jsonl)."""
    if item["scorer"] == "judge_pairwise":
        return {"correct": None, "pending": "judge"}
    return SCORERS[item["scorer"]](item, answer)
