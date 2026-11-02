# PolyMath (`polymath`)

- **Source:** Qwen/PolyMath@71e0db90
- **Paper:** Wang et al., 2025, PolyMath: Evaluating Mathematical Reasoning in Multilingual Contexts (arXiv:2504.18428)
- **Licence:** not declared on the dataset card (GitHub repo QwenLM/PolyMath: check before redistribution)
- **Scorer:** math_verify on the last \boxed{}

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 500 | 500 | 0 |
| en | 500 | 500 | 0 |

Scorer per item: `math_verify` 1000.

On by default: en/high 97, en/medium 125, it/high 97, it/medium 125.

## ID alignment between Italian and English

- ids in both languages: **500**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| gold_repaired | 7 | `polymath-medium-036` malformed LaTeX: \right\] -> \right]; `polymath-medium-111` missing closing brace restored after 2\sqrt{2} (value checked numerically against the integral: 0.6232252401); `polymath-medium-058` same matrix written as pmatrix instead of \left[\begin{array}...\right], which math_verify parses |
| gold_unscorable | 1 | `polymath-top-013` a family with constraints (alpha in {-1,0,1}, beta real) that no single expression captures; also '\alphax' is malformed |
| overlap_with_suite | 1 | `-` 28 PolyMath-high problems are also in other benchmarks of this suite: 14 in aime25, 14 in mclm_aime2024 (meta.also_in) |

Full log: [issues/polymath.jsonl](issues/polymath.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Levels medium and high are on by default (meta.default=true); low and top are in the files with meta.default=false.
- Possible contamination: the problems come from public competitions and textbooks.
- Prompt suffix is PolyMath's own per-language instruction (instruction.py, query_dic), which literally reads `$\boxed\{\}$`.
- Gold answers are stored as in the source, wrapped in `$...$`.
- Overlap within the suite: 28 PolyMath-high problems are AIME problems that are also items of aime25 (14) or mclm_aime2024 (14); meta.also_in names the twin. Decision 2026-10-15: they are off by default here and scored only in the AIME benchmarks, so the default set is medium 125 + high 97 = 222 items per language.
- Gold repairs (2026-10-15): 8 golds failed against an answer identical to them. Repaired: medium-036 and medium-111 (malformed LaTeX), medium-058 (matrix rewritten as pmatrix), top-050, top-037, top-093 (prose rewritten as the set of values or equations); each checked against correct answers in other notations and against wrong ones. Partly: top-088 (prose dropped; matches only the factored form with the letter c). Not repairable: top-013. Source golds in meta.gold_original.
- Italian: no item left untranslated; numbers and formulas carried over (the 9 number differences are localisations such as 1:00 PM -> 13:00 and .5 -> 0,5).
