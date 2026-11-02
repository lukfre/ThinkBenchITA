# LiveCodeBench (code generation, release_v3) (`livecodebench`)

- **Source:** livecodebench/code_generation_lite@0fe84c39 (test.jsonl, test2.jsonl, test3.jsonl)
- **Paper:** Jain et al., 2024, LiveCodeBench (arXiv:2403.07974)
- **Licence:** CC (as declared on the dataset card); problems come from LeetCode and AtCoder
- **Scorer:** code_exec (sandboxed): all public and private tests must pass

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 612 | 612 | 0 |
| en | 612 | 612 | 0 |

Scorer per item: `code_exec` 1224.

## ID alignment between Italian and English

- ids in both languages: **612**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

| kind | count | examples |
|---|---|---|
| repaired | 5 | `lcb-1873_A` translation edited by hand: "sÌ", "sì", "Sì" e "⟦OUT_1⟧"; `lcb-1883_B` translation edited by hand: "sÌ", "sì", "Sì" e "⟦OUT_1⟧"; `lcb-abc307_b` translation edited by hand: Nessuna coppia di stringhe distinte tra S_1, S_2 e S_3 forma un palindromo quand |

Full log: [issues/livecodebench.jsonl](issues/livecodebench.jsonl). Nothing listed here was edited in the data.

## Notes and decisions

- Window fixed to the one Olmo 3 uses: `release_v3` of code_generation_lite (OLMES task livecodebench_codegeneration, revision release_v3; the paper calls it "LiveCodeBench v3"). 612 problems, contests from 2023-05-07 to 2024-08-10.
- Italian (2026-11-02): our translation, TranslateGemma 27B (Infomaniak-AI/vllm-translategemma-27b-it) on Cineca, prose only, code and samples protected by the pipeline; every row re-checked at build time (src/loaders/translated.py; pinned by config/translation/manifest.json). Provenance in meta.translation. The statement is translated; starter code, sample inputs/outputs and tests stay as they are. The output words are Italian (src/loaders/lcb_output_words_it.json, e.g. Yes -> Sì): the statement uses them and the scorer maps the expected outputs of every test (meta.output_word_map; 56 problems). 5 sentences repaired by hand (meta.repaired): a masked "No" that was prose in 3 explanations, and the accepted spellings of the positive answer in 2 Codeforces problems.
- Prompt: LiveCodeBench's own (system message + Question/Format/Answer), as OLMES builds it. The Italian prompt is Italian throughout: system message, headings and format instructions are our translation (src/prompts.py, LCB['it']), plus the translated statement.
- 60 problems expect fixed English words in the program's output (meta.fixed_output_words: Yes/No in 51, plus First/Second, Bat/Glove, Draw, Unreachable, undecidable, infinite, san, Alice/Bob). Often unquoted in the statement ("print Yes; otherwise, print No"), so a translation that renders them in Italian makes the item unsolvable. Found by scanning every test output; 28 more problems print letters that are not language (random strings, echoed input). Plan (2026-10-15): mask these words before translating, translate them by hand, and map the expected test outputs to the Italian words (README, translation queue).
- Alternative not used: Olmo 3's variant (OLMES livecodebench_codegeneration::olmo3:adapt) adds "Provide CONCISE reasoning on how to arrive at the answer in the <think> </think> tag." under '### Format:'. Left out because models with built-in thinking already reason in that block.
- Private tests are not copied into data/: meta.private_tests_ref points to the row of the pinned Hub file and the scorer decodes it at run time.
- Olmo 3 settings for the code benchmarks: temperature 0.6, top-p 0.95, 10 samples, pass@1.
