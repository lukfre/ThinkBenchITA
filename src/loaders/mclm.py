"""MCLM (amphora/MCLM): MT-MATH100 and MT-AIME2024, machine-translated (GPT-4o) into 55 languages."""

import pandas as pd

from .. import prompts
from ..schema import Built, Issues, Item, user
from . import hf_file, register, source

REPO = "amphora/MCLM"
INFO = {
    "paper": "Son et al., 2025, Linguistic Generalizability of Test-Time Scaling in Mathematical Reasoning (arXiv:2502.17407)",
    "licence": "MIT",
    "scorer": "math_verify on the last \\boxed{}",
}


# MT-AIME2024 row -> AIME 2024 problem (matched 2026-10-15 against MathArena/aime_2024_I/_II:
# same answers, text compared word by word; rows are not in exam order).
AIME2024_PROBLEM = {
    0: "I-01", 1: "I-10", 2: "I-11", 3: "I-12", 4: "I-13", 5: "I-14", 6: "I-15", 7: "I-02", 8: "I-03", 9: "I-04",
    10: "I-05", 11: "I-06", 12: "I-07", 13: "I-08", 14: "I-09", 15: "II-01", 16: "II-10", 17: "II-11", 18: "II-12",
    19: "II-13", 20: "II-14", 21: "II-15", 22: "II-02", 23: "II-03", 24: "II-04", 25: "II-05", 26: "II-06",
    27: "II-07", 28: "II-08", 29: "II-09",
}  # fmt: skip
AIME2024_BROKEN = {
    28: "AIME 2024 II-08 (torus): MCLM's English says the torus rests on the OUTSIDE of the sphere and is EXTERNALLY tangent in both cases; the original has 'inside ... internally tangent' for r_i. As written, r_i = r_o and the gold 127 does not follow. The Italian translation copies the error.",
}
AIME2024_FLAGGED = {
    11: ("figure_missing", "AIME 2024 I-06 says 'as in the examples shown below'; the figure is not included (the problem is still well defined without it)."),
    13: ("figure_missing", "AIME 2024 I-08 relies on its figure for 'arranged in the same manner' (first circle tangent to AB, last to BC); text-only, as in the official wording."),
}


def _prompt(prefix: str, lang: str, text: str) -> str:
    if prefix == "mclm-aime2024":  # MathArena's AIME instruction, before the problem (as for aime25)
        return f"{prompts.MATHARENA_AIME[lang]}\n\n{text}"
    return prompts.with_suffix(text, prompts.MATH_STANDARD[lang])


def _build(filename: str, prefix: str) -> tuple[dict, Issues]:
    issues = Issues()
    df = pd.read_parquet(hf_file(REPO, filename))
    items = {"it": [], "en": []}
    for n, row in enumerate(df.to_dict("records")):
        for lang in items:
            text = row[lang]
            if not isinstance(text, str) or not text.strip():
                issues.add("missing_text", f"empty `{lang}` cell in row {n}", f"{prefix}-{n:03d}", lang)
                continue
            items[lang].append(
                Item(
                    id=f"{prefix}-{n:03d}",
                    lang=lang,
                    # AIME: MathArena's instruction before the problem, as for aime25; MATH100: generic suffix
                    messages=user(_prompt(prefix, lang, text)),
                    answer=str(row["answer"]),
                    scorer="math_verify",
                    meta=_meta(prefix, n, text),
                )
            )
    return items, issues


def _meta(prefix: str, n: int, text: str) -> dict:
    template = "matharena-aime-v1" if prefix == "mclm-aime2024" else "math-standard-v1"
    meta = {"source_row": n, "source_prompt": text, "template": template, "default": True}
    if prefix == "mclm-aime2024":
        meta["aime2024_problem"] = AIME2024_PROBLEM[n]
        if n in AIME2024_BROKEN:
            meta.update(broken=True, default=False)
        if n in AIME2024_FLAGGED:
            meta[AIME2024_FLAGGED[n][0]] = True
    return meta


MATH100_FIGURE_MISSING_IT = {
    40: "the English has the figure (Asymptote code: the wheel's numbers and the shaded checkerboard); the Italian drops it, so the Italian item cannot be solved",
    62: "the English has the figure (Asymptote code showing which region is shaded); the Italian drops it",
}


@register("mclm_math100")
def math100() -> Built:
    import json

    items, issues = _build("mt-math100.parquet", "mclm-math100")
    # The English rows are MATH-500 problems verbatim: attach MATH-500's id, subject and level.
    with open(hf_file("HuggingFaceH4/MATH-500", "test.jsonl"), encoding="utf-8") as f:
        math500 = {" ".join(r["problem"].split()): r for r in map(json.loads, f)}
    for en in items["en"]:
        ref = math500.get(" ".join(en.meta["source_prompt"].split()))
        if ref is None:
            issues.add("not_in_math500", "English text not found verbatim in MATH-500", en.id, "en")
            continue
        if ref["answer"].strip() != en.answer.strip():
            issues.add("answer_differs_from_math500", f"MCLM {en.answer!r}, MATH-500 {ref['answer']!r}", en.id, "en")
        extra = {"math500_id": ref["unique_id"], "subject": ref["subject"], "level": ref["level"]}
        for item in (en, *[i for i in items["it"] if i.id == en.id]):
            item.meta.update(extra)
    # Restore the two figures the Italian dropped (decision 2026-10-15): the Asymptote block is
    # code, not language, so it is copied from the English item, with the same separator. This is
    # the one place where source text is edited; it is logged and marked in meta.
    english = {i.id: i for i in items["en"]}
    for n, detail in MATH100_FIGURE_MISSING_IT.items():
        id_ = f"mclm-math100-{n:03d}"
        en_text = english[id_].meta["source_prompt"]
        start = en_text.index("[asy]")
        figure = en_text[len(en_text[:start].rstrip()):]  # separator + [asy]...[/asy] (+ anything after)
        for item in items["it"]:
            if item.id == id_ and "[asy]" not in item.meta["source_prompt"]:
                restored = item.meta["source_prompt"].rstrip() + figure
                item.messages = user(_prompt("mclm-math100", "it", restored))
                item.meta.update(figure_restored_from_english=True, source_prompt_original=item.meta["source_prompt"], source_prompt=restored)
        issues.add("figure_restored_from_english", detail + ". RESTORED: the English Asymptote block was appended to the Italian text (code only, nothing translated).", id_, "it")
    issues.add("translation_style", "mclm-math100-038: the comments inside the Asymptote code are translated (harmless); mclm-math100-057: the title pun 'Juan's Old Stamping Grounds' rendered literally as 'I Vecchi Terreni di Juan'", lang="it")
    if len(items["en"]) != 100:
        issues.add("item_count", f"the file has {len(items['en'])} rows, the paper and dataset card say 100")
    return Built(
        items,
        issues,
        {
            "name": "MCLM MT-MATH100",
            "source": source(REPO) + " (mt-math100.parquet)",
            **INFO,
            "notes": [
                "Backup for MATH-500 comparability: the English rows are MATH-500 problems verbatim (99/99 exact text matches, identical answers); meta.math500_id, meta.subject and meta.level come from HuggingFaceH4/MATH-500. The paper's 100th problem is not in the file and cannot be identified.",
                "13 problems carry an Asymptote figure as code. The Italian keeps it in 11 (in 038 only the code comments are translated) and dropped it in 2: mclm-math100-040 (unsolvable without it) and mclm-math100-062. RESTORED (2026-10-15): the English Asymptote block is appended to those two Italian items; it is code, so nothing is translated. This is the only edit to source text in this benchmark (meta.figure_restored_from_english, original text kept in meta.source_prompt_original).",
                "Prompt (2026-10-15): the de facto MATH-500 prompt for reasoning models, \"Please reason step by step, and put your final answer within \\boxed{}.\" after the problem (Italian ours: \"Ragiona passo dopo passo e scrivi la risposta finale all'interno di \\boxed{}.\").",
                "The source has no item ids; ids are the row index in the parquet file.",
                "Italian text is a GPT-4o translation of the English, not human-checked.",
                "Some problems contain Asymptote ([asy]) figures as code; kept verbatim.",
            ],
        },
    )


@register("mclm_aime2024")
def aime2024() -> Built:
    items, issues = _build("mt-aime2024.parquet", "mclm-aime2024")
    for n, detail in AIME2024_BROKEN.items():
        issues.add("broken", detail, f"mclm-aime2024-{n:03d}")
    for n, (kind, detail) in AIME2024_FLAGGED.items():
        issues.add(kind, detail, f"mclm-aime2024-{n:03d}")
    issues.add(
        "translation_style",
        "GPT-4o translation: 'relatively prime' rendered three ways ('relativamente primi', 'coprimi', 'primi tra loro'); 'inradius' as the calque 'inraggio' (mclm-aime2024-013), where 'raggio della circonferenza inscritta' is the usual term",
        lang="it",
    )
    return Built(
        items,
        issues,
        {
            "name": "MCLM MT-AIME2024",
            "source": source(REPO) + " (mt-aime2024.parquet)",
            **INFO,
            "notes": [
                "The source has no item ids; ids are the row index in the parquet file.",
                "Italian text is a GPT-4o translation of the English, not human-checked.",
                "AIME 2024 is public and widely used: contamination is likely.",
                "Prompt: MathArena's AIME instruction before the problem, as for aime25 (\"Put your final answer within \\boxed{}. The answer is an integer between 0 and 999 inclusive.\", Italian ours); all 30 answers are integers in 0-999, as AIME requires. MCLM's own code picks a system prompt per model (default 'Return your response in \\boxed{} format.', English for every language), so there is no fixed standard to follow.",
                "Rows are not in exam order; meta.aime2024_problem gives the AIME 2024 number (I-01 ... II-15), matched against MathArena's copy by answer and text. All 30 answers agree with MathArena's.",
                "The English text follows the original AoPS wording (MathArena rewrote some problems to be self-contained without figures, e.g. I-05, I-08, I-09); figures are not included.",
                "mclm-aime2024-028 (II-08) is broken in both languages: 'outside / externally' twice instead of 'inside / internally' once. Off by default (meta.default=false), not edited.",
                "Italian: numbers and formulas carried over in all 30 (checked automatically); a few style issues logged.",
            ],
        },
    )
