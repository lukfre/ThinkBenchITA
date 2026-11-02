# MCLM MT-MATH100 (`mclm_math100`)

- **Source:** amphora/MCLM@aa789e49 (mt-math100.parquet)
- **Paper:** Son et al., 2025, Linguistic Generalizability of Test-Time Scaling in Mathematical Reasoning (arXiv:2502.17407)
- **Licence:** MIT
- **Scorer:** math_verify on the last \boxed{}

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 99 | 99 | 0 |
| en | 99 | 99 | 0 |

Scorer per item: `math_verify` 198.

On by default: en/1 9, en/2 17, en/3 16, en/4 30, en/5 27, it/1 9, it/2 17, it/3 16, it/4 30, it/5 27.

## ID alignment between Italian and English

- ids in both languages: **99**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| figure_restored_from_english | 2 | `mclm-math100-040` the English has the figure (Asymptote code: the wheel's numbers and the shaded checkerboard); the Italian drops it, so the Italian item cannot be solved. RESTORED: the English Asymptote block was appended to the Italian text (code only, nothing translated).; `mclm-math100-062` the English has the figure (Asymptote code showing which region is shaded); the Italian drops it. RESTO |
| translation_style | 1 | `-` mclm-math100-038: the comments inside the Asymptote code are translated (harmless); mclm-math100-057: the title pun 'Juan's Old Stamping Grounds' rendered literally as 'I Vecchi Terreni di Juan' |
| item_count | 1 | `-` the file has 99 rows, the paper and dataset card say 100 |

Full log: [issues/mclm_math100.jsonl](issues/mclm_math100.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Backup for MATH-500 comparability: the English rows are MATH-500 problems verbatim (99/99 exact text matches, identical answers); meta.math500_id, meta.subject and meta.level come from HuggingFaceH4/MATH-500. The paper's 100th problem is not in the file and cannot be identified.
- 13 problems carry an Asymptote figure as code. The Italian keeps it in 11 (in 038 only the code comments are translated) and dropped it in 2: mclm-math100-040 (unsolvable without it) and mclm-math100-062. RESTORED (2026-10-15): the English Asymptote block is appended to those two Italian items; it is code, so nothing is translated. This is the only edit to source text in this benchmark (meta.figure_restored_from_english, original text kept in meta.source_prompt_original).
- Prompt (2026-10-15): the de facto MATH-500 prompt for reasoning models, "Please reason step by step, and put your final answer within \boxed{}." after the problem (Italian ours: "Ragiona passo dopo passo e scrivi la risposta finale all'interno di \boxed{}.").
- The source has no item ids; ids are the row index in the parquet file.
- Italian text is a GPT-4o translation of the English, not human-checked.
- Some problems contain Asymptote ([asy]) figures as code; kept verbatim.
