# X-AlpacaEval (`xalpaca`)

- **Source:** zhihz0535/X-AlpacaEval@4dc0165d (italian.json, english.json)
- **Paper:** Zhang et al., 2024, PLUG: Leveraging Pivot Language in Cross-Lingual Instruction Tuning (ACL 2024); Li et al., 2023, AlpacaEval
- **Licence:** CC BY-NC 4.0
- **Scorer:** judge_pairwise: an LLM judge compares the model output with a reference output

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 805 | 805 | 0 |
| en | 805 | 805 | 0 |

Scorer per item: `judge_pairwise` 1610.

## ID alignment between Italian and English

- ids in both languages: **805**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| repaired | 1 | `xalpaca-0031` mistranslation: 'How do I detail a car?' had become 'Come si curano i dettagli di un'auto?' (how do you take care of a car's details); car 'detailing' is a deep, complete cleaning. REPAIRED (wording chosen by the project, 2026-10-15). |

Full log: [issues/xalpaca.jsonl](issues/xalpaca.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- The Italian instructions are professional human translations of the 805 AlpacaEval instructions.
- X-AlpacaEval item n is AlpacaEval instruction n-1: same English text and subset for all 805 (checked against tatsu-lab/alpaca_eval).
- Judge model to be changed (2026-10-15): GPT-4 Turbo is too expensive to judge every run, so a cheaper judge will replace it; the setup (prompt, probability-based preference, random position, LC) stays. With a non-standard judge the numbers are no longer AlpacaEval 2's, and the meta-evaluation against human judgments is needed in English too.
- Judge setup (2026-10-15): AlpacaEval 2's (annotator weighted_alpaca_eval_gpt4_turbo): judge GPT-4 Turbo (gpt-4-1106-preview), AlpacaEval's prompt (English verbatim; Italian runs use our translation, src/prompts.py ALPACA_JUDGE), preference from the judge's probabilities of the ids m/M, output position randomised per item with a fixed seed.
- Reference outputs: English uses AlpacaEval 2's official GPT-4 Turbo outputs; Italian has none and is generated from the Italian instructions with gpt-4-1106-preview (xalpaca_reference.py).
- Metrics: raw win rate and AlpacaEval 2's length-controlled win rate (v1), plus its unregularised variant. Synthetic check: v1 lowers the win rate of outputs that are systematically longer than the reference even when the verdicts ignore length (coin flip: raw 50.9, v1 35.8, noreg 50.0), because it regularises towards AlpacaEval's English length-gamed baselines.
- Not validated for Italian yet (README, To do): the length correction, which uses English-derived instruction difficulties, and the judge itself, which needs a meta-evaluation against human judgments in Italian.
- xalpaca-0031 was mistranslated ('How do I detail a car?' -> 'Come si curano i dettagli di un'auto?'; car detailing is a deep clean). REPAIRED (2026-10-15): 'Come si fa pulizia accurata e completa, all'interno e all'esterno, di un'automobile?'; original in meta.source_prompt_original.
