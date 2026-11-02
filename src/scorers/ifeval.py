"""IFEval scorer: Multi-IF's checkers (vendored, unmodified logic), strict and loose.

`correct` is the strict, prompt-level result (every instruction followed), the
number IFEval and Multi-IF report as "strict accuracy".
"""

from functools import lru_cache


@lru_cache(maxsize=1)
def _checkers():
    import nltk

    for resource, path in (("punkt", "tokenizers/punkt"), ("punkt_tab", "tokenizers/punkt_tab")):
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(resource, quiet=True)
    from .vendor import multi_if_ifeval

    return multi_if_ifeval


def _follows(instruction_id: str, kwargs: dict, responses: list[str]) -> bool:
    ifeval = _checkers()
    instruction = ifeval.INSTRUCTION_DICT[instruction_id](instruction_id)
    instruction.build_description(**kwargs)
    return any(r.strip() and instruction.check_following(r) for r in responses)


def loose_variants(response: str) -> list[str]:
    """The 8 relaxed readings of a response used by IFEval's loose accuracy."""
    lines = response.split("\n")
    variants = [response, "\n".join(lines[1:]).strip(), "\n".join(lines[:-1]).strip(), "\n".join(lines[1:-1]).strip()]
    return variants + [v.replace("*", "") for v in variants]


def score_ifeval(item: dict, answer: str) -> dict:
    ids, kwargs = item["meta"]["instruction_id_list"], item["meta"]["kwargs"]
    strict = [_follows(i, k, [answer]) for i, k in zip(ids, kwargs)]
    loose = [_follows(i, k, loose_variants(answer)) for i, k in zip(ids, kwargs)]
    return {
        "correct": all(strict),
        "correct_loose": all(loose),
        "follow_strict": strict,
        "follow_loose": loose,
        "instruction_id_list": ids,
    }
