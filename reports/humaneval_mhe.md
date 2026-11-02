# mHumanEval-Expert (alternative Italian HumanEval) (`humaneval_mhe`)

- **Source:** github.com/mraihan-gmu/mHumanEval-Benchmark@b4ac5b3f (mHuamnEval-Expert/Human_Expert_ita_Latn.json); tests: evalplus/humanevalplus@d32357cf; alignment check: openai/openai_humaneval@7dce6050
- **Paper:** Raihan et al., 2025, mHumanEval (NAACL 2025, arXiv:2410.15037); Liu et al., 2023, EvalPlus (NeurIPS 2023)
- **Licence:** mHumanEval: Apache 2.0 (repo LICENSE); HumanEval+: Apache 2.0; HumanEval: MIT
- **Scorer:** code_exec (sandboxed) with the HumanEval+ tests

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 164 | 164 | 0 |
| en | – (no English side) | | |

Scorer per item: `code_exec` 164.

## ID alignment between Italian and English

- single-language benchmark: nothing to align.

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| content_problem | 40 | `HumanEval/17` value the function must return/accept translated: o\|; `HumanEval/19` value the function must return/accept translated: eight, five, four, nine, one, seven, six, three, two; `HumanEval/63` content dropped |
| prompt_differs_from_humaneval | 1 | `HumanEval/115` HumanEval+ ships a corrected prompt; the Italian translation was made from the original HumanEval text |

Full log: [issues/humaneval_mhe.jsonl](issues/humaneval_mhe.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- NOT the Italian side of `humaneval`: kept as a reported alternative, off by default (decision 2026-10-15). The Italian side of `humaneval` will be our own translation.
- 40 of 164 items have content problems (meta.quality_problems), 4 of them recoverable by putting back an English value: truncated docstrings, rules or examples dropped, values the tests check translated (e.g. 'one'..'nine' -> 'uno'..'nove', "YES" -> "Sì"), example strings translated into wrong examples. About 50 more have their line breaks collapsed. Side-by-side of all problem items: reports/samples/humaneval_problems.md.
- Despite the "Expert" name, the text appears to start from mHumanEval's own machine translation (mHumanEval-max/mHumanEval-ita_Latn-python), with the doctests restored: several sentences are identical.
- ID alignment: the file has no task ids; rows are in HumanEval order. 164/164 rows pass all three checks (entry point present, identical `def` line, original HumanEval test contained). Code, signatures and >>> doctests are identical to HumanEval in all 164.
- Scored with the HumanEval+ tests, so numbers are not comparable with mHumanEval's published ones (original tests).
