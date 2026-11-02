# HumanEval+ (`humaneval`)

- **Source:** evalplus/humanevalplus@d32357cf; prompt check against openai/openai_humaneval@7dce6050
- **Paper:** Chen et al., 2021 (HumanEval); Liu et al., 2023, EvalPlus (NeurIPS 2023)
- **Licence:** HumanEval+: Apache 2.0; HumanEval: MIT
- **Scorer:** code_exec (sandboxed) with the HumanEval+ tests

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 164 | 164 | 0 |
| en | 164 | 164 | 0 |

Scorer per item: `code_exec` 328.

On by default: en/None 163, it/None 163.

## ID alignment between Italian and English

- ids in both languages: **164**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| prompt_differs_from_humaneval | 1 | `HumanEval/115` HumanEval+ ships a corrected prompt (translate this one, not the original HumanEval text) |
| reference_solution_fails_its_test | 1 | `HumanEval/32` failed: TypeError: Value after * must be an iterable, not float |

Full log: [issues/humaneval.jsonl](issues/humaneval.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Italian (2026-11-02): our translation, TranslateGemma 27B (Infomaniak-AI/vllm-translategemma-27b-it) on Cineca, prose only, code and samples protected by the pipeline; every row re-checked at build time (src/loaders/translated.py; pinned by config/translation/manifest.json). Provenance in meta.translation. Translated from the HumanEval+ prompt; rule, also in meta.translation_rule: Translate the prose of the docstring only. Keep unchanged: code, signature, identifiers, doctest lines (>>> and their output), example calls and their results, and every quoted value (strings the function must accept or return).
- Why not mHumanEval-Expert, the source named in the instructions: 40 of its 164 Italian items have content problems (36 not recoverable without translating again). It is kept as the alternative benchmark `humaneval_mhe`; see reports/humaneval_mhe.md and reports/samples/humaneval_problems.md.
- HumanEval/32 (find_zero): the `test` string of evalplus/humanevalplus rejects its own reference solution (logged as reference_solution_fails_its_test), so no answer can pass it. Off by default in both languages (meta.default=false, 2026-11-02; was kept until then), not edited: the suite scores 163 items.
- Prompt (2026-10-15): EvalPlus's own chat instruction, as for MBPP+: "Please provide a self-contained Python script that solves the following problem in a markdown code block:", then the HumanEval+ prompt (signature + docstring) in a ``` block, as EvalPlus builds it; the assistant turn is not prefilled. Italian instruction: our translation (EVALPLUS['it']). Replaces our earlier wording (code-complete-v1).
