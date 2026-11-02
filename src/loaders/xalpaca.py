"""X-AlpacaEval (zhihz0535/X-AlpacaEval): 805 parallel instructions, judged pairwise."""

import json

from ..schema import Built, Issues, Item, user
from . import hf_file, register, source

REPO = "zhihz0535/X-AlpacaEval"
FILES = {"it": "italian.json", "en": "english.json"}
IT_REPAIRS = {
    "xalpaca-0031": (
        "Come si fa pulizia accurata e completa, all'interno e all'esterno, di un'automobile?",
        "mistranslation: 'How do I detail a car?' had become 'Come si curano i dettagli di un'auto?' (how do you take care of a car's details); "
        "car 'detailing' is a deep, complete cleaning. REPAIRED (wording chosen by the project, 2026-10-15).",
    ),
}


@register("xalpaca")
def build() -> Built:
    issues = Issues()
    items = {}
    for lang, filename in FILES.items():
        with open(hf_file(REPO, filename), encoding="utf-8") as f:
            rows = json.load(f)
        items[lang] = [
            Item(
                id=f"xalpaca-{row['id']:04d}",
                lang=lang,
                messages=user(row["instruction"]),
                answer=None,  # judged against a reference output, see scripts/xalpaca_reference.py
                scorer="judge_pairwise",
                meta={"subset": row["dataset"], "source_id": row["id"], "template": "none"},
            )
            for row in rows
        ]
    # Repair (decision 2026-10-15): the one mistranslation found, re-translated by us; original kept in meta.
    for item in items["it"]:
        if item.id in IT_REPAIRS:
            new_text, why = IT_REPAIRS[item.id]
            item.meta.update(repaired=True, source_prompt_original=item.messages[0]["content"])
            item.messages = user(new_text)
            issues.add("repaired", why, item.id, "it")
    subsets = {lang: {i.id: i.meta["subset"] for i in rows} for lang, rows in items.items()}
    for id_, subset in subsets["it"].items():
        if subsets["en"].get(id_) != subset:
            issues.add("subset_mismatch", f"it={subset} en={subsets['en'].get(id_)}", id_)
    return Built(
        items,
        issues,
        {
            "name": "X-AlpacaEval",
            "source": source(REPO) + " (italian.json, english.json)",
            "paper": "Zhang et al., 2024, PLUG: Leveraging Pivot Language in Cross-Lingual Instruction Tuning (ACL 2024); Li et al., 2023, AlpacaEval",
            "licence": "CC BY-NC 4.0",
            "scorer": "judge_pairwise: an LLM judge compares the model output with a reference output",
            "notes": [
                "The Italian instructions are professional human translations of the 805 AlpacaEval instructions.",
                "X-AlpacaEval item n is AlpacaEval instruction n-1: same English text and subset for all 805 (checked against tatsu-lab/alpaca_eval).",
                "Judge model to be changed (2026-10-15): GPT-4 Turbo is too expensive to judge every run, so a cheaper judge will replace it; the setup (prompt, probability-based preference, random position, LC) stays. With a non-standard judge the numbers are no longer AlpacaEval 2's, and the meta-evaluation against human judgments is needed in English too.",
                "Judge setup (2026-10-15): AlpacaEval 2's (annotator weighted_alpaca_eval_gpt4_turbo): judge GPT-4 Turbo (gpt-4-1106-preview), AlpacaEval's prompt (English verbatim; Italian runs use our translation, src/prompts.py ALPACA_JUDGE), preference from the judge's probabilities of the ids m/M, output position randomised per item with a fixed seed.",
                "Reference outputs: English uses AlpacaEval 2's official GPT-4 Turbo outputs; Italian has none and is generated from the Italian instructions with gpt-4-1106-preview (xalpaca_reference.py).",
                "Metrics: raw win rate and AlpacaEval 2's length-controlled win rate (v1), plus its unregularised variant. Synthetic check: v1 lowers the win rate of outputs that are systematically longer than the reference even when the verdicts ignore length (coin flip: raw 50.9, v1 35.8, noreg 50.0), because it regularises towards AlpacaEval's English length-gamed baselines.",
                "Not validated for Italian yet (README, To do): the length correction, which uses English-derived instruction difficulties, and the judge itself, which needs a meta-evaluation against human judgments in Italian.",
                "xalpaca-0031 was mistranslated ('How do I detail a car?' -> 'Come si curano i dettagli di un'auto?'; car detailing is a deep clean). REPAIRED (2026-10-15): 'Come si fa pulizia accurata e completa, all'interno e all'esterno, di un'automobile?'; original in meta.source_prompt_original.",
            ],
        },
    )
