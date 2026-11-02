# Task: prepare Italian (+ parallel English) evaluation benchmarks for vLLM

## Goal
Inspect each benchmark below and convert it into a unified format that our vLLM evaluation harness can run. Every benchmark needs an Italian version and, where possible, the parallel English version with matching item IDs. We evaluate reasoning models: outputs contain a thinking block followed by a final answer. A vLLM wrapper is available in src/ folder.

## Unified format
One JSONL file per benchmark × language, e.g. `data/{benchmark}/{lang}.jsonl`, with fields:
- `id`: stable item ID, identical across languages for parallel items
- `lang`: `it` or `en`
- `messages`: chat-format prompt (list of {role, content})
- `answer`: gold answer (string / list), or null for judge-scored tasks
- `scorer`: one of `math_verify`, `mcq`, `code_exec`, `ifeval`, `judge_pairwise`
- `meta`: source-specific fields (difficulty level, subject, test cases, instruction IDs, etc.)

Do not modify the text of prompts or gold answers beyond format conversion. If something needs fixing, record it in a log; don't silently edit.

## Benchmarks

1. **PolyMath** — `Qwen/PolyMath` *(verify ID)*. Use `it` and `en`, levels `medium` and `high` (keep `low`/`top` available but off by default). Scorer: `math_verify` on `\boxed{}`. Note in the README: possible contamination (sources are public competitions).
2. **MCLM MT-MATH100 and MT-AIME2024** — `amphora/MCLM` *(verify ID)*. Italian + English. Scorer: `math_verify`. MT-MATH100 is a backup for MATH-500 comparability.
3. **AIME25** — no Italian version exists. Prepare the English side (30 problems) and an empty Italian file with matching IDs, to be filled by our translation pipeline later.
4. **INVALSI MATE** — from the CALAMITA 2024 INVALSI paper (Puccetti et al., CLiC-it 2024); locate the official release from the paper. Italian only. Diagnostic set: tag `meta.diagnostic=true`. Check the answer format (MCQ vs open) and pick the scorer accordingly.
5. **GPQA** — Italian: `ellamind/gpqa-multilingual`, config `ita`; English: `Idavidrein/gpqa` (gated). Keep the 448 main set and the `is_diamond` flag. Scorer: `mcq`. Shuffle options with a fixed seed, using the same permutation for IT and EN. Preserve the GPQA canary string in stored files; do not push the data to any public location.
6. **Zebra** — English: ZebraLogic (`allenai/ZebraLogicBench` *(verify ID)*). Italian: will be generated with the MultiZebraLogic generator (`github.com/alexandrainst/zebra_puzzles`). For now: inspect the generator, check what is needed to add Italian, and report. Scorer: exact grid match.
7. **mHumanEval** — `github.com/mraihan-gmu/mHumanEval-Benchmark`, Italian **Expert** subset (human-translated, all 164 problems). Attach the EvalPlus HumanEval+ tests (`evalplus/humanevalplus`) by task ID; verify that all 164 IDs align. English: HumanEval+ directly. Scorer: `code_exec` (sandboxed).
8. **MBPP+** and **LiveCodeBench** — no Italian versions. Prepare the English side (`evalplus/mbppplus`; LiveCodeBench code generation, fix the release/date window used by OLMo 3) and empty Italian files for later translation of problem statements only. Tests stay unchanged.
9. **Multi-IF** — `facebook/Multi-IF`, Italian and English, **turn 1 only**. Scorer: IFEval checkers. Check which instruction types depend on language (keywords, letter frequency, capitalisation, word counts) and report how the Multi-IF code handles them in Italian.
10. **X-AlpacaEval** — `zhihz0535/X-AlpacaEval`, splits `italian` and `english` (805 parallel instructions, CC BY-NC). Scorer: `judge_pairwise`. Reference outputs don't exist in Italian: prepare a script that generates them with a fixed reference model from the Italian instructions (config placeholder for model name), and a judge config (placeholder for judge model; judge prompt in Italian, fixed across all runs).

## Generation / scoring requirements
- vLLM with the model's chat template; configurable sampling (temperature, top_p, max_tokens, n for pass@k).
- Split each output into thinking and final answer. Score only the final answer; keep the thinking.
- Save raw outputs (prompt, thinking, answer, tokens) per item, because we compute trace metrics on them afterwards (language compliance with Lingua, step-level language switches, length, repetition, termination -- these live in another folder and are already taken care of by another agent).
- Report pass@1 and pass@k per benchmark × language.

## Deliverables
1. Loader for each benchmark.
2. An inspection report per benchmark: item counts per language, ID alignment between IT and EN, missing or malformed items, licence, and anything that needed a decision.
3. A random sample of 20 IT/EN item pairs per benchmark exported side by side (for our manual translation check).
4. A README listing each benchmark, its source/paper, scorer, and caveats.