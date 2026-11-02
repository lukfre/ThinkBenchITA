"""HumanEval+ in English and Italian.

`humaneval`      English: HumanEval+. Italian: placeholders, to be translated by our
                 pipeline from the HumanEval+ prompts (docstring prose only).
`humaneval_mhe`  Alternative Italian side, mHumanEval-Expert (Italian only, off by
                 default): 40 of its 164 items have content problems, flagged in meta.
"""

import json
import re

import pandas as pd

from .. import prompts
from pathlib import Path

from ..schema import Built, Issues, Item, placeholder, user
from . import translated
from . import github_file, hf_file, register, source

GH_REPO = "mraihan-gmu/mHumanEval-Benchmark"
GH_COMMIT = "b4ac5b3f59bb8a9b27fabd2d63080963995b1388"
GH_PATH = "mHuamnEval-Expert/Human_Expert_ita_Latn.json"  # sic: the directory name has this typo upstream
PLUS = "evalplus/humanevalplus"
ORIG = "openai/openai_humaneval"
MHE_PROBLEMS = json.loads((Path(__file__).parent / "mhumaneval_problems.json").read_text(encoding="utf-8"))["items"]
TRANSLATION_RULE = (
    "Translate the prose of the docstring only. Keep unchanged: code, signature, identifiers, doctest lines (>>> and their "
    "output), example calls and their results, and every quoted value (strings the function must accept or return)."
)


def _signature(prompt: str, entry_point: str) -> str | None:
    m = re.search(rf"^def {re.escape(entry_point)}\(.*$", prompt, re.M)
    return m.group(0).strip() if m else None


def _item(task_id, lang, prompt, plus_row, extra) -> Item:
    return Item(
        id=task_id,
        lang=lang,
        messages=user(prompts.evalplus_prompt(lang, prompt)),
        answer=None,
        scorer="code_exec",
        meta={
            "entry_point": plus_row["entry_point"],
            "test": plus_row["test"],  # HumanEval+ test: defines check(candidate)
            "test_format": "humaneval",
            "canonical_solution": plus_row["canonical_solution"],
            "source_prompt": prompt,
            "template": "evalplus-instruct-v1",
            **extra,
        },
    )


@register("humaneval_mhe")
def build_mhe() -> Built:
    issues = Issues()
    plus = pd.read_parquet(hf_file(PLUS, "data/test-00000-of-00001-5973903632b82d40.parquet")).to_dict("records")
    orig = pd.read_parquet(hf_file(ORIG, "openai_humaneval/test-00000-of-00001.parquet")).to_dict("records")
    with open(github_file(GH_REPO, GH_COMMIT, GH_PATH), encoding="utf-8") as f:
        ita = [json.loads(line) for line in f if line.strip()]

    en = [_item(p["task_id"], "en", p["prompt"], p, {}) for p in plus]
    for p, o in zip(plus, orig):
        if p["task_id"] != o["task_id"]:
            issues.add("id_order", f"HumanEval+ row {p['task_id']} vs HumanEval row {o['task_id']}")
        elif p["prompt"] != o["prompt"]:
            issues.add("prompt_differs_from_humaneval", "HumanEval+ ships a corrected prompt; the Italian translation was made from the original HumanEval text", p["task_id"])

    # The Italian file has no task ids: rows are in HumanEval order. Check every
    # row three ways before trusting the order.
    if len(ita) != len(plus):
        issues.add("item_count", f"Italian file has {len(ita)} rows, HumanEval+ has {len(plus)}")
    it, aligned = [], 0
    for n, (row, p, o) in enumerate(zip(ita, plus, orig)):
        tid = p["task_id"]
        checks = {
            "entry_point": f"def {p['entry_point']}(" in row["prompt"],
            "signature": _signature(row["prompt"], p["entry_point"]) == _signature(o["prompt"], p["entry_point"]),
            # the Italian file carries the original HumanEval test (without the METADATA header)
            "test": row["test"].strip() in o["test"],
        }
        failed = [k for k, ok in checks.items() if not ok]
        if failed:
            issues.add("alignment", f"row {n} does not match {tid} on: {', '.join(failed)}", tid, "it")
        else:
            aligned += 1
        if row["prompt"].strip() == o["prompt"].strip():
            issues.add("untranslated", "Italian prompt is identical to the English one", tid, "it")
        flags = {}
        if tid in MHE_PROBLEMS:
            flags = {"quality_problems": MHE_PROBLEMS[tid]["problems"], "recoverable": MHE_PROBLEMS[tid]["recoverable"]}
            issues.add("content_problem", "; ".join(MHE_PROBLEMS[tid]["problems"]), tid, "it")
        it.append(_item(tid, "it", row["prompt"], p, {"source_row": n, "alignment_checks": checks, **flags}))
    n_bad = sum(tid in MHE_PROBLEMS for tid in (i.id for i in it))
    n_rec = sum(MHE_PROBLEMS[i.id]["recoverable"] for i in it if i.id in MHE_PROBLEMS)
    return Built(
        {"it": it},
        issues,
        {
            "name": "mHumanEval-Expert (alternative Italian HumanEval)",
            "source": f"github.com/{GH_REPO}@{GH_COMMIT[:8]} ({GH_PATH}); tests: {source(PLUS)}; alignment check: {source(ORIG)}",
            "paper": "Raihan et al., 2025, mHumanEval (NAACL 2025, arXiv:2410.15037); Liu et al., 2023, EvalPlus (NeurIPS 2023)",
            "licence": "mHumanEval: Apache 2.0 (repo LICENSE); HumanEval+: Apache 2.0; HumanEval: MIT",
            "scorer": "code_exec (sandboxed) with the HumanEval+ tests",
            "notes": [
                "NOT the Italian side of `humaneval`: kept as a reported alternative, off by default (decision 2026-10-15). The Italian side of `humaneval` will be our own translation.",
                f"{n_bad} of {len(it)} items have content problems (meta.quality_problems), {n_rec} of them recoverable by putting back an English value: truncated docstrings, rules or examples dropped, values the tests check translated (e.g. 'one'..'nine' -> 'uno'..'nove', \"YES\" -> \"Sì\"), example strings translated into wrong examples. About 50 more have their line breaks collapsed. Side-by-side of all problem items: reports/samples/humaneval_problems.md.",
                "Despite the \"Expert\" name, the text appears to start from mHumanEval's own machine translation (mHumanEval-max/mHumanEval-ita_Latn-python), with the doctests restored: several sentences are identical.",
                f"ID alignment: the file has no task ids; rows are in HumanEval order. {aligned}/{len(ita)} rows pass all three checks (entry point present, identical `def` line, original HumanEval test contained). Code, signatures and >>> doctests are identical to HumanEval in all 164.",
                "Scored with the HumanEval+ tests, so numbers are not comparable with mHumanEval's published ones (original tests).",
            ],
        },
    )


# HumanEval+ `test` that rejects its own reference solution: `_poly(*candidate(*inp), inp)` unpacks the returned float
BROKEN = {"HumanEval/32"}


@register("humaneval")
def build() -> Built:
    issues = Issues()
    plus = pd.read_parquet(hf_file(PLUS, "data/test-00000-of-00001-5973903632b82d40.parquet")).to_dict("records")
    orig = pd.read_parquet(hf_file(ORIG, "openai_humaneval/test-00000-of-00001.parquet")).to_dict("records")
    en = [_item(p["task_id"], "en", p["prompt"], p, {"default": p["task_id"] not in BROKEN}) for p in plus]
    for p, o in zip(plus, orig):
        if p["task_id"] != o["task_id"]:
            issues.add("id_order", f"HumanEval+ row {p['task_id']} vs HumanEval row {o['task_id']}")
        elif p["prompt"] != o["prompt"]:
            issues.add("prompt_differs_from_humaneval", "HumanEval+ ships a corrected prompt (translate this one, not the original HumanEval text)", p["task_id"])
    it = [
        placeholder(e, translate=["source_prompt"], translation_rule=TRANSLATION_RULE, template="evalplus-instruct-v1",
                    keep=["entry_point", "test", "test_format", "canonical_solution", "default"])
        for e in en
    ]
    it = translated.fill("humaneval", en, it, issues)
    return Built(
        {"it": it, "en": en},
        issues,
        {
            "name": "HumanEval+",
            "source": f"{source(PLUS)}; prompt check against {source(ORIG)}",
            "paper": "Chen et al., 2021 (HumanEval); Liu et al., 2023, EvalPlus (NeurIPS 2023)",
            "licence": "HumanEval+: Apache 2.0; HumanEval: MIT",
            "scorer": "code_exec (sandboxed) with the HumanEval+ tests",
            "notes": [
                "Italian (2026-11-02): our translation, TranslateGemma 27B (Infomaniak-AI/vllm-translategemma-27b-it) on Cineca, prose only, code and samples protected by the pipeline; every row re-checked at build time (src/loaders/translated.py; pinned by config/translation/manifest.json). Provenance in meta.translation. Translated from the HumanEval+ prompt; rule, also in meta.translation_rule: " + TRANSLATION_RULE,
                "Why not mHumanEval-Expert, the source named in the instructions: 40 of its 164 Italian items have content problems (36 not recoverable without translating again). It is kept as the alternative benchmark `humaneval_mhe`; see reports/humaneval_mhe.md and reports/samples/humaneval_problems.md.",
                "HumanEval/32 (find_zero): the `test` string of evalplus/humanevalplus rejects its own reference solution (logged as reference_solution_fails_its_test), so no answer can pass it. Off by default in both languages (meta.default=false, 2026-11-02; was kept until then), not edited: the suite scores 163 items.",
                "Prompt (2026-10-15): EvalPlus's own chat instruction, as for MBPP+: \"Please provide a self-contained Python script that solves the following problem in a markdown code block:\", then the HumanEval+ prompt (signature + docstring) in a ``` block, as EvalPlus builds it; the assistant turn is not prefilled. Italian instruction: our translation (EVALPLUS['it']). Replaces our earlier wording (code-complete-v1).",
            ],
        },
    )
