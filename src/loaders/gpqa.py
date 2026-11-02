"""GPQA main (448 questions): English from Idavidrein/gpqa, Italian from ellamind/gpqa-multilingual.

Both repos are gated ("do not reveal examples online"). The data written by
this loader must stay local: data/ is git-ignored, and every stored row
carries the GPQA canary string in `meta.canary`.
"""

import json
import random
from pathlib import Path

import pandas as pd

from .. import prompts
from ..schema import Built, Issues, Item, user
from . import SourceUnavailable, hf_file, register, source, subset

EN_REPO = "Idavidrein/gpqa"
IT_REPO = "ellamind/gpqa-multilingual"
SEED = 20261006
LETTERS = "ABCD"
# The Italian file lists each question's incorrect answers in a different order from the
# English CSV (random per item). This index-only table puts them back in the English order,
# so that the same permutation gives the same option under the same letter in both languages.
DISTRACTOR_ORDER = json.loads((Path(__file__).parent / "gpqa_it_distractor_order.json").read_text())

# Found on 2026-10-15 reading the items (both languages; not edited).
SOURCE_PROBLEMS = {
    "recDjE01bu72pPUU2": ("duplicate_options", "two options are the same text, one of them the gold: a model choosing the twin letter is scored wrong"),
    "recoiTJPGUmzAkief": ("duplicate_options", "two options are the same text, one of them the gold: a model choosing the twin letter is scored wrong"),
    "recZSGUkn56v9kEp1": ("duplicate_options", "two incorrect options are the same text (the item still has one right answer)"),
    "recnGEpF1srQpaqWq": ("duplicate_options", "two incorrect options are the same text (the item still has one right answer)"),
    "recLrRirj7iXoB0rU": ("truncated_option", "one incorrect option starts mid-formula (with \\rangle): its first ket is missing"),
    "recYCMJWH7IpcdqwE": ("typo_in_option", "an incorrect option has a stray step label (\"HNO3/H2SO4 iv) ;\")"),
}


def permutation(record_id: str) -> list[int]:
    """Option order for one question: a function of the seed and the record id
    only, so Italian and English get the same order whatever the row order."""
    order = list(range(4))
    random.Random(f"{SEED}:{record_id}").shuffle(order)
    return order


# Which prompt format to build: "olmo3" (default, as Olmo 3 evaluates GPQA) or "simple-evals".
TEMPLATE = "olmo3"
# Items whose gold answer text also appears as a second option: a model choosing the twin
# letter is scored wrong. Kept in the set for now (decision 2026-10-15), flagged in meta.
DUPLICATED_GOLD = {"recDjE01bu72pPUU2", "recoiTJPGUmzAkief"}


def render(lang: str, question: str, options: list[str], template: str = TEMPLATE) -> str:
    if template == "olmo3":
        t = prompts.GPQA_OLMO3[lang]
        choices = "".join(f" ({LETTERS[k]}) {text}\n" for k, text in enumerate(options))
        return t["description"] + t["question"] + question + t["choices"] + choices + t["final"]
    if template == "simple-evals":
        return prompts.GPQA_SIMPLE_EVALS[lang].format(question=question, **dict(zip(LETTERS, options)))
    raise ValueError(template)


def make_item(record_id, lang, question, correct, incorrect, meta) -> Item:
    options = [correct, *incorrect]  # index 0 is the gold answer before shuffling
    order = permutation(record_id)
    shuffled = [options[i] for i in order]
    flags = {"gold_duplicated": True} if record_id in DUPLICATED_GOLD else {}
    return Item(
        id=f"gpqa-{record_id}",
        lang=lang,
        messages=user(render(lang, question, shuffled)),
        answer=LETTERS[order.index(0)],
        scorer="mcq",
        meta={
            "choices": list(LETTERS),
            "options": shuffled,
            "permutation": order,
            "shuffle_seed": SEED,
            "template": f"gpqa-{TEMPLATE}-v1",
            "source_prompt": {"question": question, "correct_answer": correct, "incorrect_answers": list(incorrect)},
            "default": record_id not in DUPLICATED_GOLD,  # off since 2026-11-02
            **flags,
            **meta,
        },
    )


@register("gpqa_main")
def build() -> Built:
    issues = Issues()
    items = {"it": [], "en": []}
    canary, diamond_en = None, None

    try:
        main = pd.read_csv(hf_file(EN_REPO, "gpqa_main.csv"))
        diamond_en = set(pd.read_csv(hf_file(EN_REPO, "gpqa_diamond.csv"))["Record ID"])
        canaries = main["Canary String"].dropna().unique()
        canary = canaries[0] if len(canaries) else None
        if len(canaries) != 1:
            issues.add("canary", f"{len(canaries)} distinct canary strings in gpqa_main.csv")
        for row in main.to_dict("records"):
            items["en"].append(
                make_item(
                    row["Record ID"],
                    "en",
                    row["Question"],
                    row["Correct Answer"],
                    [row[f"Incorrect Answer {k}"] for k in (1, 2, 3)],
                    {
                        "is_diamond": row["Record ID"] in diamond_en,
                        "domain": row.get("High-level domain"),
                        "subdomain": row.get("Subdomain"),
                        "canary": row.get("Canary String"),
                    },
                )
            )
    except SourceUnavailable as e:
        issues.add("source_unavailable", str(e), lang="en")

    try:
        ita = pd.read_parquet(hf_file(IT_REPO, "ita/train-00000-of-00001.parquet"))
        for row in ita.to_dict("records"):
            rid = row["original_id"]
            order = DISTRACTOR_ORDER["order"].get(rid)
            if order is None:
                issues.add("distractor_order_unknown", "no entry in gpqa_it_distractor_order.json: Italian distractors left in source order", f"gpqa-{rid}", "it")
                order = [0, 1, 2]
            if diamond_en is not None and bool(row["is_diamond"]) != (rid in diamond_en):
                issues.add("is_diamond_mismatch", f"ita says {row['is_diamond']}, gpqa_diamond.csv says {rid in diamond_en}", f"gpqa-{rid}")
            if row.get("flag_for_review"):
                # the translating model's opinion about the ENGLISH item (answer key, premise), not about its translation
                issues.add("translator_flag_on_source", str(row.get("review_reason")), f"gpqa-{rid}", "it")
            items["it"].append(
                make_item(
                    rid,
                    "it",
                    row["question"],
                    row["correct_answer"],
                    [list(row["incorrect_answers"])[j] for j in order],
                    {
                        "is_diamond": bool(row["is_diamond"]),
                        "domain": row.get("domain"),
                        "subdomain": row.get("subdomain"),
                        "canary": canary,
                        "translation_confidence": row.get("translation_confidence"),
                        "flag_for_review": bool(row.get("flag_for_review")),
                    },
                )
            )
        if canary is None:
            issues.add("canary", "English source unavailable, so the Italian rows carry no canary string yet; rebuild once access is granted", lang="it")
    except SourceUnavailable as e:
        issues.add("source_unavailable", str(e), lang="it")

    for rid, (kind, detail) in SOURCE_PROBLEMS.items():
        issues.add(kind, detail, f"gpqa-{rid}")
    for rows in items.values():
        rows.sort(key=lambda i: i.id)  # the two sources list the questions in different orders

    return Built(
        items,
        issues,
        {
            "name": "GPQA (main, 448)",
            "source": f"en: {source(EN_REPO)} (gpqa_main.csv); it: {source(IT_REPO)} (config ita)",
            "paper": "Rein et al., 2024, GPQA: A Graduate-Level Google-Proof Q&A Benchmark (arXiv:2311.12022)",
            "licence": "CC BY 4.0, gated: do not reveal examples in plain text online",
            "scorer": "mcq (letters A-D)",
            "notes": [
                "DO NOT publish data/gpqa/. The directory is git-ignored; every row keeps the GPQA canary string in meta.canary.",
                f"Options are shuffled with seed {SEED}; the permutation depends on the record id only, so it is identical in Italian and English (meta.permutation).",
                "meta.is_diamond marks the 198-question Diamond subset.",
                "The Italian side is a Gemini 3.1 Pro translation (ellamind/gpqa-multilingual).",
                "Distractor order: the Italian file shuffles each item's three incorrect answers relative to the English CSV. They are put back in the English order with src/loaders/gpqa_it_distractor_order.json (indices only; 423 items matched automatically by two agreeing methods, 25 by hand), so each letter shows the same option in both languages.",
                "The translating model flagged 39 items (kind translator_flag_on_source, meta.flag_for_review). Its flags are about the ENGLISH items, mostly claims that the answer key or the premise is wrong; they are not verified and not translation problems. GPQA's own paper reports expert disagreement on part of the set.",
                "Checked automatically: no untranslated question, formulas and numbers carried over (the 15 questions where they differ are rewordings: digits written as words, thousand separators, extra math mode), Italian decimal commas exactly where English has them.",
                "Prompt: Olmo 3's format (OLMES gpqa::olmo3:adapt): instruction, then \"Question: ... Choices: (A) ...\", then the instruction repeated; the answer must end with \"Therefore, the answer is (X)\". Template gpqa-olmo3-v1; the Italian (\"Quindi, la risposta è (X)\") is our translation. Two differences from OLMES: options are not passed through its `_preprocess` (which deletes any [bracketed] text), and the option order is our seeded permutation, not OLMES's.",
                "Alternative prompt, not used: OpenAI simple-evals (\"Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' ... Think step by step before answering.\"), the format most reasoning-model reports use for GPQA. Set TEMPLATE = \"simple-evals\" in src/loaders/gpqa.py to build it (template gpqa-simple-evals-v1, Italian also ours).",
                "OFF BY DEFAULT (2026-11-02; kept in the set until then): gpqa-recDjE01bu72pPUU2 and gpqa-recoiTJPGUmzAkief have their gold answer duplicated as a second option (meta.gold_duplicated=true, meta.default=false). A model picking the twin letter would be scored wrong, so these 2 items cannot be answered reliably. The suite scores 446 items (Diamond 197). Not edited.",
                "Source problems found reading the items: 4 items with duplicated options (2 where the duplicate is the gold, so they cannot be answered reliably), 1 truncated option, 1 typo in an option. Same in both languages; not edited.",
                "Ids are `gpqa-{Record ID}`.",
            ],
        },
    )


@register("gpqa")
def build_diamond() -> Built:
    return subset(build(), lambda i: i.meta["is_diamond"] and i.meta["default"], "GPQA Diamond",
                  "What the suite runs (2026-11-02): the Diamond items of GPQA main (both expert validators agree with the key, most non-experts fail), minus gpqa-recoiTJPGUmzAkief, whose gold answer is listed twice: 197 of Diamond's 198. All of GPQA main (448) is `gpqa_main`, off in the suite.")
