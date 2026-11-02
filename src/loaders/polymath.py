"""PolyMath (Qwen/PolyMath): 4 levels x 125 problems, parallel across languages."""

import json
from pathlib import Path

import pandas as pd

from .. import prompts
from ..schema import Built, Issues, Item, user
from . import hf_file, register, source

REPO = "Qwen/PolyMath"
LEVELS = ["low", "medium", "high", "top"]
DEFAULT_LEVELS = ["medium", "high"]
OVERLAP = json.loads((Path(__file__).parent / "polymath_overlap.json").read_text())["also_in"]
# Gold answers repaired on 2026-10-15 (decision: repair what is fixable). Found by scoring every
# gold against an answer identical to it: these failed. Each repair was checked with math_verify
# against correct answers in other notations and against wrong answers (see reports/polymath.md).
# The source gold is kept in meta.gold_original.
GOLD_REPAIRS = {
    "polymath-medium-036": (r"$\left[ \frac{b_1(q^m - 2)}{m}, \frac{b_1q^m}{m} \right]$",
                            "malformed LaTeX: \\right\\] -> \\right]"),
    "polymath-medium-111": (r"$\frac{1}{2\sqrt{2}} \ln\frac{\sqrt{2}+2}{2-\sqrt{2}}$",
                            "missing closing brace restored after 2\\sqrt{2} (value checked numerically against the integral: 0.6232252401)"),
    "polymath-medium-058": (r"$\begin{pmatrix} \frac{1}{2} e^{-t} & 0 & \frac{1}{2} e^{-t} \\ \frac{1}{2} \cos t+\frac{1}{2} \sin t & -\sin t & \frac{1}{2} \sin t-\frac{1}{2} \cos t \\ \frac{1}{2} \sin t-\frac{1}{2} \cos t & \cos t & -\frac{1}{2} \cos t-\frac{1}{2} \sin t \end{pmatrix}$",
                            "same matrix written as pmatrix instead of \\left[\\begin{array}...\\right], which math_verify parses"),
    "polymath-top-050": (r"$4, 16, 65536, 2^{256}$", "prose '2^{2^l} for l=1,2,4,8' written as the set of its four values"),
    "polymath-top-037": (r"$-\frac{3^{1010}-1}{2}, -\frac{3^{1010}-1}{2} + \frac{\sqrt{9^{1010}-1}}{4}i, -\frac{3^{1010}-1}{2} - \frac{\sqrt{9^{1010}-1}}{4}i$",
                         "prose '... and ... \\pm ...' written as the set of its three values"),
    "polymath-top-093": (r"$f(x)=0, f(x)=x^2$", "prose '... and ...' written as a set of two equations"),
    "polymath-top-088": (r"$P(x)=c(x^2+3)$", "prose 'for any constant c' dropped; PARTIAL: matches only the factored form with the letter c"),
}
# Golds still not matchable (kept, flagged, off by default with their level).
UNSCORABLE_GOLD = {
    "polymath-top-013": "a family with constraints (alpha in {-1,0,1}, beta real) that no single expression captures; also '\\alphax' is malformed",
}
PARTIAL_GOLD = {"polymath-top-088"}


@register("polymath")
def build() -> Built:
    issues = Issues()
    items = {"it": [], "en": []}
    for lang in items:
        for level in LEVELS:
            df = pd.read_parquet(hf_file(REPO, f"{lang}/{level}.parquet"))
            for row in df.itertuples():
                # source ids are "{level}-{lang}-{n}"; ours drop the language
                lvl, src_lang, n = row.id.split("-")
                if (lvl, src_lang) != (level, lang):
                    issues.add("id_mismatch", f"id {row.id} in {lang}/{level}", row.id, lang)
                items[lang].append(
                    Item(
                        id=f"polymath-{level}-{int(n):03d}",
                        lang=lang,
                        messages=user(prompts.with_suffix(row.question, prompts.POLYMATH[lang])),
                        answer=GOLD_REPAIRS.get(f"polymath-{level}-{int(n):03d}", (row.answer,))[0],
                        scorer="math_verify",
                        meta={
                            "level": level,
                            # off by default: other levels, unscorable golds, and problems that are also
                            # items of aime25 / mclm_aime2024 (decision 2026-10-15: AIME is scored there)
                            "default": level in DEFAULT_LEVELS and f"polymath-{level}-{int(n):03d}" not in UNSCORABLE_GOLD
                            and f"polymath-{level}-{int(n):03d}" not in OVERLAP,
                            **({"also_in": OVERLAP[f"polymath-{level}-{int(n):03d}"]} if f"polymath-{level}-{int(n):03d}" in OVERLAP else {}),
                            **({"gold_unscorable": True} if f"polymath-{level}-{int(n):03d}" in UNSCORABLE_GOLD else {}),
                            **({"gold_repaired": True, "gold_original": row.answer} if f"polymath-{level}-{int(n):03d}" in GOLD_REPAIRS else {}),
                            **({"gold_partially_scorable": True} if f"polymath-{level}-{int(n):03d}" in PARTIAL_GOLD else {}),
                            "source_id": row.id,
                            "source_prompt": row.question,
                            "template": "polymath-official",
                        },
                    )
                )
    for id_, why in UNSCORABLE_GOLD.items():
        issues.add("gold_unscorable", why, id_)
    for id_, (_, why) in GOLD_REPAIRS.items():
        issues.add("gold_repaired", why, id_)
    issues.add("overlap_with_suite", f"{len(OVERLAP)} PolyMath-high problems are also in other benchmarks of this suite: "
               f"{sum(v.startswith('aime25') for v in OVERLAP.values())} in aime25, {sum(v.startswith('mclm') for v in OVERLAP.values())} in mclm_aime2024 (meta.also_in)")
    en = {i.id: i for i in items["en"]}
    for it in items["it"]:
        if it.id in en and it.answer != en[it.id].answer:
            issues.add("answer_differs_across_langs", f"it={it.answer!r} en={en[it.id].answer!r}", it.id)
    return Built(
        items,
        issues,
        {
            "name": "PolyMath",
            "source": source(REPO),
            "paper": "Wang et al., 2025, PolyMath: Evaluating Mathematical Reasoning in Multilingual Contexts (arXiv:2504.18428)",
            "licence": "not declared on the dataset card (GitHub repo QwenLM/PolyMath: check before redistribution)",
            "scorer": "math_verify on the last \\boxed{}",
            "notes": [
                "Levels medium and high are on by default (meta.default=true); low and top are in the files with meta.default=false.",
                "Possible contamination: the problems come from public competitions and textbooks.",
                "Prompt suffix is PolyMath's own per-language instruction (instruction.py, query_dic), which literally reads `$\\boxed\\{\\}$`.",
                "Gold answers are stored as in the source, wrapped in `$...$`.",
                "Overlap within the suite: 28 PolyMath-high problems are AIME problems that are also items of aime25 (14) or mclm_aime2024 (14); meta.also_in names the twin. Decision 2026-10-15: they are off by default here and scored only in the AIME benchmarks, so the default set is medium 125 + high 97 = 222 items per language.",
                "Gold repairs (2026-10-15): 8 golds failed against an answer identical to them. Repaired: medium-036 and medium-111 (malformed LaTeX), medium-058 (matrix rewritten as pmatrix), top-050, top-037, top-093 (prose rewritten as the set of values or equations); each checked against correct answers in other notations and against wrong ones. Partly: top-088 (prose dropped; matches only the factored form with the letter c). Not repairable: top-013. Source golds in meta.gold_original.",
                "Italian: no item left untranslated; numbers and formulas carried over (the 9 number differences are localisations such as 1:00 PM -> 13:00 and .5 -> 0,5).",
            ],
        },
    )
