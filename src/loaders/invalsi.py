"""INVALSI MATE (Puccetti, Cassese, Esuli; CALAMITA @ CLiC-it 2024). Italian only, diagnostic.

Built as the paper builds it: every question is multiple choice. `numero` questions
get four options, the gold and the authors' three distractors (alt1-alt3); the 20
`completa frase` items, which the paper excludes, stay in the file off by default.
Unlike the paper (likelihood scoring), the model must GENERATE its choice.
"""

import random
import re

import pandas as pd

from .. import prompts
from ..schema import Built, Issues, Item, user
from . import hf_file, register, source

REPO = "ai4text/Invalsi"
SEED = 20261015
LETTERS = "ABCD"

# Found reading the items on 2026-10-15 (not edited).
BROKEN = {
    "invalsi-mate-271": "no question and no options: the context text is repeated twice; the gold 'C' refers to nothing",
}
FLAGGED = {
    "invalsi-mate-074": ("options_not_lettered", "the four options are listed without letters; the gold 'A' means the first one"),
    "invalsi-mate-157": ("gold_duplicated", "distractor alt3 equals the gold (20): the right answer appears under two letters"),
    "invalsi-mate-289": ("typo", "\"Se si sostituisce con un numero naturale\": the variable 'a' is missing after 'sostituisce'; still readable"),
}
OFF = {"invalsi-mate-074", "invalsi-mate-157"}  # flagged items off by default (2026-11-02); 289 stays on


def _letters(text: str) -> list[str]:
    """Option letters written in the question or its context ("\\nA 5 ore", "A. Viola", "A: 15 euro")."""
    return sorted(set(re.findall(r"(?:^|[\s\"])([A-D])[.):]?(?=\s)", text)))


def numero_options(id_: str, gold: str, distractors: list[str]) -> tuple[list[str], str]:
    """Gold + distractors in a seeded order that depends on the item id only."""
    options = [gold, *distractors]
    order = list(range(len(options)))
    random.Random(f"{SEED}:{id_}").shuffle(order)
    shuffled = [options[i] for i in order]
    return shuffled, LETTERS[order.index(0)]


@register("invalsi_mate")
def build() -> Built:
    issues = Issues()
    df = pd.read_csv(hf_file(REPO, "invalsi_mate.csv"), dtype=str, keep_default_na=False)
    items = []
    for n, row in enumerate(df.to_dict("records")):
        id_ = f"invalsi-mate-{n:03d}"
        text = f"{row['testo']}\n\n{row['domanda']}"
        gold, kind = row["risposta"], row["tipo"]
        meta = {
            "diagnostic": True,
            "type": kind,
            "test_id": row["test_id"],  # {year}_{grade}_{test}
            "grade": row["test_id"].split("_")[1] if row["test_id"].count("_") >= 1 else None,
            "source_row": n,
            "source_prompt": {"testo": row["testo"], "domanda": row["domanda"]},
            # the paper's benchmark: 400 items, every type except completa frase
            "official": kind != "completa frase",
        }
        if kind == "multipla":
            scorer, answer, suffix, meta["template"] = "mcq", gold, prompts.MCQ["it"], "mcq-v1"
            meta["choices"] = list(LETTERS)
            found = _letters(text)
            if (len(found) < 2 or gold not in found) and id_ not in BROKEN and id_ not in FLAGGED:
                issues.add("options_unclear", f"gold {gold!r}, option letters found: {found}", id_, "it")
                meta["options_unclear"] = True
        elif kind == "vero/falso":
            scorer, answer, suffix, meta["template"] = "mcq", gold, prompts.TRUE_FALSE_IT, "tf-v1"
            meta["choices"] = ["V", "F"]
        elif kind == "numero":
            distractors = [row[k] for k in ("alt1", "alt2", "alt3") if row[k]]
            if len(distractors) != 3:
                issues.add("distractors", f"{len(distractors)} distractors instead of 3", id_, "it")
            options, answer = numero_options(id_, gold, distractors)
            text += "\n" + "\n".join(f"{LETTERS[k]}. {o}" for k, o in enumerate(options))
            scorer, suffix, meta["template"] = "mcq", prompts.MCQ["it"], "mcq-v1"
            meta.update(choices=list(LETTERS[: len(options)]), options=options, gold_value=gold, distractors=distractors)
        elif kind == "completa frase":
            scorer, answer, suffix, meta["template"] = "exact_match", gold, prompts.EXACT_IT, "exact-v1"
            meta["autoscore_unreliable"] = True
        else:
            issues.add("unknown_type", kind, id_, "it")
            continue
        if id_ in BROKEN:
            meta["broken"] = True
            issues.add("broken", BROKEN[id_], id_, "it")
        if id_ in FLAGGED:
            flag, detail = FLAGGED[id_]
            meta[flag] = True
            issues.add(flag, detail, id_, "it")
        meta["default"] = meta["official"] and not meta.get("broken", False) and id_ not in OFF
        items.append(Item(id=id_, lang="it", messages=user(prompts.with_suffix(text, suffix)), answer=answer, scorer=scorer, meta=meta))
    n_default = sum(i.meta["default"] for i in items)
    return Built(
        {"it": items},
        issues,
        {
            "name": "INVALSI MATE",
            "source": source(REPO) + " (invalsi_mate.csv, split `validation`)",
            "paper": "Puccetti, Cassese, Esuli, 2024, INVALSI - Mathematical and Language Understanding in Italian: A CALAMITA Challenge (CLiC-it 2024, aclanthology.org/2024.clicit-1.129)",
            "licence": "not declared on the dataset card; the items are INVALSI test questions",
            "scorer": "mcq (generated letter), for every item of the benchmark",
            "notes": [
                "Diagnostic set: every item has meta.diagnostic=true; report it separately from the main results. Italian only.",
                "Format choice (2026-10-15): multiple choice answered by GENERATION. The paper turns every question into multiple choice and scores by likelihood: scelta multipla and vero/falso are multiple choice already, numero gets four options (the gold plus the authors' distractors alt1-alt3), and the 20 completa frase items are excluded, giving 400 items. We keep the paper's items and options but let the model reason and write its letter, since we evaluate reasoning models. This is easier than open-ended answers, but it keeps the benchmark diverse, and it avoids a real ambiguity of open scoring: several numero questions ask for part of the answer (invalsi-mate-120 asks for the exponent, the gold is 10^26) or are phrased as fill-in-the-blank.",
                f"On by default (meta.default): {n_default} items = the paper's 400 minus invalsi-mate-271, which is broken, and the two flagged items (074, 157; off since 2026-11-02, 399 before). The 20 completa frase items stay in the file with meta.official=false, scored by exact_match (unreliable on free-form answers), off by default.",
                f"numero options are shuffled with seed {SEED}; the order depends on the item id only (meta.options; meta.gold_value keeps the gold as written in the source). Options are added after the question as 'A. ...' lines; scelta multipla items show their options as written in the source, so they are not shuffled.",
                "Prompt: source text (testo, blank line, domanda), then our Italian instruction 'Rispondi con la lettera dell'opzione corretta, nel formato \"Risposta: X\".' (true/false: 'Rispondi con V (vero) o F (falso)...'). There is no official generative prompt: the paper only scores likelihoods.",
                "Figures: 28 items mention a picture, a table or a box ('osserva', 'in figura'). All were read: tables and boxes are given inline as text and the pictures are decorative, so every item is answerable from the text.",
                "Item problems (issue log): invalsi-mate-271 broken (excluded by default); invalsi-mate-074 options without letters and invalsi-mate-157 gold also among the distractors (off by default since 2026-11-02, not edited); invalsi-mate-289 small typo.",
                "Numeric options keep the source's decimal point (e.g. 6.12) even where the question text uses a decimal comma.",
            ],
        },
    )
