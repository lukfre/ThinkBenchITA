# GPQA (main, 448) (`gpqa_main`)

- **Source:** en: Idavidrein/gpqa@83022cef (gpqa_main.csv); it: ellamind/gpqa-multilingual@bc70ca17 (config ita)
- **Paper:** Rein et al., 2024, GPQA: A Graduate-Level Google-Proof Q&A Benchmark (arXiv:2311.12022)
- **Licence:** CC BY 4.0, gated: do not reveal examples in plain text online
- **Scorer:** mcq (letters A-D)

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 448 | 448 | 0 |
| en | 448 | 448 | 0 |

Scorer per item: `mcq` 896.

On by default: en/None 446, it/None 446.

## ID alignment between Italian and English

- ids in both languages: **448**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| translator_flag_on_source | 39 | (details in the local issue log) |
| duplicate_options | 4 | (details in the local issue log) |
| truncated_option | 1 | (details in the local issue log) |
| typo_in_option | 1 | (details in the local issue log) |

Full log: `data/gpqa_main/issues.jsonl` (local only). Nothing listed here was edited in the data.

## Notes and decisions

- DO NOT publish data/gpqa/. The directory is git-ignored; every row keeps the GPQA canary string in meta.canary.
- Options are shuffled with seed 20261006; the permutation depends on the record id only, so it is identical in Italian and English (meta.permutation).
- meta.is_diamond marks the 198-question Diamond subset.
- The Italian side is a Gemini 3.1 Pro translation (ellamind/gpqa-multilingual).
- Distractor order: the Italian file shuffles each item's three incorrect answers relative to the English CSV. They are put back in the English order with src/loaders/gpqa_it_distractor_order.json (indices only; 423 items matched automatically by two agreeing methods, 25 by hand), so each letter shows the same option in both languages.
- The translating model flagged 39 items (kind translator_flag_on_source, meta.flag_for_review). Its flags are about the ENGLISH items, mostly claims that the answer key or the premise is wrong; they are not verified and not translation problems. GPQA's own paper reports expert disagreement on part of the set.
- Checked automatically: no untranslated question, formulas and numbers carried over (the 15 questions where they differ are rewordings: digits written as words, thousand separators, extra math mode), Italian decimal commas exactly where English has them.
- Prompt: Olmo 3's format (OLMES gpqa::olmo3:adapt): instruction, then "Question: ... Choices: (A) ...", then the instruction repeated; the answer must end with "Therefore, the answer is (X)". Template gpqa-olmo3-v1; the Italian ("Quindi, la risposta è (X)") is our translation. Two differences from OLMES: options are not passed through its `_preprocess` (which deletes any [bracketed] text), and the option order is our seeded permutation, not OLMES's.
- Alternative prompt, not used: OpenAI simple-evals ("Answer the following multiple choice question. The last line of your response should be of the following format: 'Answer: $LETTER' ... Think step by step before answering."), the format most reasoning-model reports use for GPQA. Set TEMPLATE = "simple-evals" in src/loaders/gpqa.py to build it (template gpqa-simple-evals-v1, Italian also ours).
- OFF BY DEFAULT (2026-11-02; kept in the set until then): gpqa-recDjE01bu72pPUU2 and gpqa-recoiTJPGUmzAkief have their gold answer duplicated as a second option (meta.gold_duplicated=true, meta.default=false). A model picking the twin letter would be scored wrong, so these 2 items cannot be answered reliably. The suite scores 446 items (Diamond 197). Not edited.
- Source problems found reading the items: 4 items with duplicated options (2 where the duplicate is the gold, so they cannot be answered reliably), 1 truncated option, 1 typo in an option. Same in both languages; not edited.
- Ids are `gpqa-{Record ID}`.
