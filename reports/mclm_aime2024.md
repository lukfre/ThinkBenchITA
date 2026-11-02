# MCLM MT-AIME2024 (`mclm_aime2024`)

- **Source:** amphora/MCLM@aa789e49 (mt-aime2024.parquet)
- **Paper:** Son et al., 2025, Linguistic Generalizability of Test-Time Scaling in Mathematical Reasoning (arXiv:2502.17407)
- **Licence:** MIT
- **Scorer:** math_verify on the last \boxed{}

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 30 | 30 | 0 |
| en | 30 | 30 | 0 |

Scorer per item: `math_verify` 60.

On by default: en/None 29, it/None 29.

## ID alignment between Italian and English

- ids in both languages: **30**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| figure_missing | 2 | `mclm-aime2024-011` AIME 2024 I-06 says 'as in the examples shown below'; the figure is not included (the problem is still well defined without it).; `mclm-aime2024-013` AIME 2024 I-08 relies on its figure for 'arranged in the same manner' (first circle tangent to AB, last to BC); text-only, as in the official wording. |
| broken | 1 | `mclm-aime2024-028` AIME 2024 II-08 (torus): MCLM's English says the torus rests on the OUTSIDE of the sphere and is EXTERNALLY tangent in both cases; the original has 'inside ... internally tangent' for r_i. As written, r_i = r_o and the gold 127 does not follow. The Italian translation copies the error. |
| translation_style | 1 | `-` GPT-4o translation: 'relatively prime' rendered three ways ('relativamente primi', 'coprimi', 'primi tra loro'); 'inradius' as the calque 'inraggio' (mclm-aime2024-013), where 'raggio della circonferenza inscritta' is the usual term |

Full log: [issues/mclm_aime2024.jsonl](issues/mclm_aime2024.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- The source has no item ids; ids are the row index in the parquet file.
- Italian text is a GPT-4o translation of the English, not human-checked.
- AIME 2024 is public and widely used: contamination is likely.
- Prompt: MathArena's AIME instruction before the problem, as for aime25 ("Put your final answer within \boxed{}. The answer is an integer between 0 and 999 inclusive.", Italian ours); all 30 answers are integers in 0-999, as AIME requires. MCLM's own code picks a system prompt per model (default 'Return your response in \boxed{} format.', English for every language), so there is no fixed standard to follow.
- Rows are not in exam order; meta.aime2024_problem gives the AIME 2024 number (I-01 ... II-15), matched against MathArena's copy by answer and text. All 30 answers agree with MathArena's.
- The English text follows the original AoPS wording (MathArena rewrote some problems to be self-contained without figures, e.g. I-05, I-08, I-09); figures are not included.
- mclm-aime2024-028 (II-08) is broken in both languages: 'outside / externally' twice instead of 'inside / internally' once. Off by default (meta.default=false), not edited.
- Italian: numbers and formulas carried over in all 30 (checked automatically); a few style issues logged.
