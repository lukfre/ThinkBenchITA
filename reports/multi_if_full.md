# Multi-IF (turn 1) (`multi_if_full`)

- **Source:** facebook/Multi-IF@0ab97ce0 (multiIF_20241018.csv)
- **Paper:** He et al., 2024, Multi-IF: Benchmarking LLMs on Multi-Turn and Multilingual Instructions Following (arXiv:2410.15553)
- **Licence:** CC BY-NC 2.0 (data); checker code Apache 2.0
- **Scorer:** ifeval: Multi-IF's instruction checkers (vendored), strict and loose

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 493 | 493 | 0 |
| en | 909 | 909 | 0 |

Scorer per item: `ifeval` 1402.

On by default: en/None 492, it/None 492.

## ID alignment between Italian and English

- ids in both languages: **492**
- only in Italian: **1** (`multiif-3691-2`)
- only in English: **417** (`multiif-1000-1`, `multiif-1019-15`, `multiif-1019-16`, `multiif-1021-3`, `multiif-1040-16`, `multiif-1040-5`, `multiif-1051-10`, `multiif-1051-16`, `multiif-1087-18`, `multiif-1087-3` …)

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| repaired | 5 | `multiif-1922-5` the Italian prompt drops the 'first repeat the request word for word' instruction; the checker (combination:repeat_prompt) still requires it. REPAIRED: appended our Italian translation of the missing instruction; English: "Let's repeat all text above word by word, then reply to the request above. Do NOT say anything before repeating the text above."; `multiif-1922-9` the Italian p |
| prompt_kwarg_mismatch | 4 | `multiif-337-3` the prompt asks for at least 400 words, the checker requires 336 (lenient; both languages); `multiif-337-15` the prompt asks for at least 400 words, the checker requires 336 (lenient; both languages); `multiif-337-15` the prompt asks for at least 400 words, the checker requires 336 (lenient; both languages) |
| italian_prompt_mentions_english | 2 | `multiif-3329-14` Ehi! Ho bisogno di una griglia di valutazione per valutare le prestazioni e il prezzo di un laptop. Puoi creare un esempio per me? Non darmi punti elenco, liste; `multiif-3329-6` Ehi! Ho bisogno di una rubrica per valutare le prestazioni e il prezzo di un laptop. Puoi creare un esempio per me? Non darmi punti elenco, liste o tabelle. Scr |
| outer_quotes_removed | 1 | `-` 127 Italian prompts were wrapped whole in double quotes (no English prompt is); the outer pair was removed. Inner quotes are untouched; originals in meta.source_prompt_original. |

Full log: [issues/multi_if_full.jsonl](issues/multi_if_full.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Turn 1 only: the prompt is `turn_1_prompt`, checked against `turn_1_instruction_id_list` / `turn_1_kwargs`. No suffix is added.
- Ids are the source key without the language (`multiif-{prompt}-{variant}`); the English file has 909 rows and the Italian 493, so only the shared ids are parallel. The suite runs the 492 shared ids in both languages (`multi_if`; meta.default): the 417 English-only items bring instruction types the Italian file lacks (change case, response language, more keyword checks), and multiif-3691-2 has no English twin. Every item is in `multi_if_full`, off in the suite.
- How the checkers behave on Italian text is described in reports/multi_if_language.md.
- Prompt-checker consistency (2026-10-15): every checker argument (counts, keywords, end phrases, text to repeat) was looked up in its prompt, and every argument-free instruction (no commas, title, JSON, quotes...) was looked for in the wording. Count conversions like 'at most 150 words' checked as 'fewer than 151' are correct. Real problems, Italian only: 4 prompts drop an instruction the checker still applies (multiif-1922-5, -1922-9, -288-9: the 'repeat the request' instruction; multiif-3245-3: 'no commas, 2 placeholders'), 1 keyword differs from its checker (multiif-2662-10). Two more (multiif-2716-1, -8: 'use il at most once') were nearly impossible in Italian because the checker counted 'il' inside any word; fixed by the checker change below. Both languages: multiif-337-3 and -15 ask for 400 words but check for 336 (lenient). REPAIRED (2026-10-15): the 4 dropped instructions are restored with our Italian translation of the English sentence, and multiif-2662-10 now asks for the keyword its checker tests ('impegna'); meta.repaired, original prompt in meta.source_prompt_original. The 400/336 pair is flagged, not edited.
- Outer quotes (2026-10-15): 127 Italian prompts, and no English one, were wrapped whole in a pair of double quotes, a translation artefact. It made the prompts read as quoted text and could fail the 'repeat the request' checker (which expects the text without quotes). The outer pair is removed; inner quotes are kept; meta.outer_quotes_removed, original in meta.source_prompt_original.
- Checker change (2026-10-15, both languages): keywords:existence and keywords:frequency match whole words (Unicode-aware; punctuation and elided articles are boundaries; keywords taken literally), where Multi-IF searches substrings with a regex. It concerns 61 Italian and 137 English instructions; on those, scores are not identical to Multi-IF's reference code. Marked in src/scorers/vendor/multi_if_ifeval.py.
