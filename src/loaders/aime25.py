"""AIME 2025: English from MathArena, Italian from AIME2025-Multilingual (a translation of the same text)."""

import re

import pandas as pd

from .. import prompts
from ..schema import Built, Issues, Item, user
from . import hf_file, register, source

EN_REPO = "MathArena/aime_2025"
IT_REPO = "fedric95/AIME2025-Multilingual"

# Found reading the Italian translations against the English (2026-10-15). Meaning is
# preserved in all of them; logged for the record, not edited.
STYLE_NOTES = {
    "aime25-I-10": "\"pesantemente delineati\" is a calque of \"heavily outlined\"; \"bordati in grassetto\" would be natural",
    "aime25-II-03": "\"rosso è solido, blu è tratteggiato\": \"solid\" is \"continuo\" for a line; \"segmenti di linea unitaria\" is awkward (\"segmenti unitari\")",
    "aime25-II-12": "`$11$-sided` became \"con 11 lati\" and \"11-gono\" in plain text, outside math mode (harmless)",
}
COPRIME_PHRASES = ("relativamente primi", "primi tra loro")


def _multilingual(lang: str) -> pd.DataFrame:
    parts = [
        pd.read_parquet(hf_file(IT_REPO, f"{lang}/aime_2025_{part}-00000-of-00001.parquet")).assign(part=part)
        for part in ("I", "II")
    ]
    df = pd.concat(parts)
    # rows are stored in string order of the problem number (1, 10, 11, ..., 2, ...)
    return df.assign(n=df["id"].astype(int)).sort_values(["part", "n"]).reset_index(drop=True)


def _same(a: str, b: str) -> bool:
    return " ".join(a.split()) == " ".join(b.split())


def _item(id_, lang, problem, answer, meta) -> Item:
    instruction = prompts.MATHARENA_AIME[lang]
    return Item(
        id=id_,
        lang=lang,
        messages=user(f"{instruction}\n\n{problem}"),
        answer=str(answer),
        scorer="math_verify",
        meta={"source_prompt": problem, "template": "matharena-aime-v1", **meta},
    )


@register("aime25")
def build() -> Built:
    issues = Issues()
    arena = pd.read_parquet(hf_file(EN_REPO, "data/train-00000-of-00001.parquet")).sort_values("problem_idx").reset_index(drop=True)
    ml_en, ml_it = _multilingual("english"), _multilingual("italian")
    if not (len(arena) == len(ml_en) == len(ml_it) == 30):
        issues.add("item_count", f"MathArena {len(arena)}, multilingual en {len(ml_en)}, it {len(ml_it)}; expected 30")

    en, it = [], []
    for k, row in arena.iterrows():
        part, n = ("I", k + 1) if k < 15 else ("II", k - 14)
        id_ = f"aime25-{part}-{n:02d}"
        meta = {"exam": f"AIME 2025 {part}", "problem": n, "problem_type": [str(t) for t in row["problem_type"]]}
        en.append(_item(id_, "en", row["problem"], row["answer"], meta))

        en_ml, it_ml = ml_en.iloc[k], ml_it.iloc[k]
        if (en_ml["part"], en_ml["n"]) != (part, n) or (it_ml["part"], it_ml["n"]) != (part, n):
            issues.add("alignment", f"row {k}: multilingual en {en_ml['part']}-{en_ml['n']}, it {it_ml['part']}-{it_ml['n']}", id_)
        # the Italian was translated from the multilingual repo's English: it must be MathArena's text
        if not _same(en_ml["problem"], row["problem"]):
            issues.add("translation_source_differs", "the English the Italian was translated from is not MathArena's current text", id_)
        if int(it_ml["answer"]) != int(row["answer"]):
            issues.add("answer_differs_across_langs", f"it={it_ml['answer']} en={row['answer']}", id_)
        it.append(_item(id_, "it", it_ml["problem"], row["answer"], {**meta, "translation": "machine (GPT-4o / Claude 3.7 Sonnet), checked by hand by the dataset authors"}))

    for item in it:
        if item.id in STYLE_NOTES:
            issues.add("translation_style", STYLE_NOTES[item.id], item.id, "it")
    coprime = {p: [i.id for i in it if p in i.meta["source_prompt"]] for p in COPRIME_PHRASES}
    if all(coprime.values()):
        issues.add(
            "translation_style",
            f"\"relatively prime\" is rendered both as \"relativamente primi\" ({', '.join(coprime['relativamente primi'])}) "
            f"and as \"primi tra loro\" ({', '.join(coprime['primi tra loro'])}); the second is the usual Italian term",
            lang="it",
        )
    figures = [i.id for i in en if re.search(r"\\begin\{(tikzpicture|asy)\}", i.meta["source_prompt"])]
    return Built(
        {"it": it, "en": en},
        issues,
        {
            "name": "AIME 2025",
            "source": f"en: {source(EN_REPO)}; it: {source(IT_REPO)} (config italian)",
            "paper": "MAA American Invitational Mathematics Examination 2025 (I and II); MathArena (Dekoninck et al., 2026, arXiv:2605.00674); AIME2025-Multilingual (Ricciuti & D'Amato, 2025)",
            "licence": "CC BY-NC-SA 4.0 (MathArena). The multilingual card says MIT, but its English is MathArena's text, so the NC-SA terms apply to it too. Problems © MAA.",
            "scorer": "math_verify on the last \\boxed{}",
            "notes": [
                "There is no official machine-readable AIME: MAA publishes the exam as booklets. MathArena's copy (extracted, converted to LaTeX and verified for the MathArena leaderboard) is used as the reference English text.",
                "The Italian is AIME2025-Multilingual's translation of that same text: four candidates per problem (2x GPT-4o, 2x Claude 3.7 Sonnet), GPT-4o picks one, then a manual check by the authors. The build checks that its English still equals MathArena's, problem by problem.",
                "Prompt: MathArena's instruction placed before the problem, as MathArena does (template matharena-aime-v1). The Italian instruction is our translation; MathArena has none.",
                f"{len(figures)} problems carry their figure as TikZ or Asymptote code in both languages: {', '.join(figures)}.",
                "Translation style issues are in the issue log (kind translation_style); none changes the mathematics.",
                "Ids follow the exam order: aime25-I-01 ... aime25-II-15. Previous sources (opencompass/AIME2025, yentinglin/aime_2025) were dropped: their Part II is a looser re-transcription, and they drop figures.",
            ],
        },
    )
