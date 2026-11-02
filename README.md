# ThinkBenchITA

Benchmarks for reasoning models in Italian, with the parallel English side, so that a model can be compared with itself across the two languages item by item. One unified format, run with vLLM on models that think before answering (a thinking block, then the final answer). Only the final answer is scored. The thinking is kept and checked: format, loops, length, and whether a model asked in Italian thinks in Italian.

**Status (2026-11-02): beta.** 12 benchmarks run end to end, in both languages (INVALSI is Italian only); checked on 5-15 items per file with Qwen3-4B-Thinking-2507, no full-size run yet. X-AlpacaEval is built but waits for its judge. Open points: [docs/decisions.md](docs/decisions.md), To do.

## Quickstart

```bash
uv sync --extra gen                 # see Install
uv run hf auth login                # an account in minerva-post-training that accepted GPQA's terms (see Get the data)
uv run python fetch_data.py         # the benchmarks, into data/
uv run python run_eval.py --run qwen3-4b --model-config config/models/qwen3-4b-thinking-2507.yaml --gpus 0 1
# results: runs/qwen3-4b/summary.md and report.md
```

## Benchmarks

| domain | benchmark | items it / en | what it tests | Italian side |
|---|---|---|---|---|
| math | PolyMath (medium + high) | 222 / 222 | competition-level word problems | GPT-4o, edited by professional translators |
| math | MCLM MT-MATH100 | 99 / 99 | high-school competition math (MATH-500), levels 1–5 | GPT-4o |
| math | MCLM MT-AIME2024 | 29 / 29 | AIME 2024: hard olympiad-qualifier problems | GPT-4o |
| math | AIME 2025 | 30 / 30 | AIME 2025, recent, less likely seen in training | LLM, checked by hand by its authors |
| math | INVALSI MATE | 397 / – | Italian national school tests, grades 2–13 (diagnostic) | native Italian |
| science | GPQA Diamond | 197 / 197 | graduate-level biology, physics, chemistry, the expert-validated subset | Gemini 3.1 Pro |
| code | HumanEval+ | 163 / 163 | Python functions from a docstring, hidden tests | ours (TranslateGemma 27B, checked) |
| code | MBPP+ | 378 / 378 | basic Python tasks, hidden tests | ours (TranslateGemma 27B, checked) |
| code | LiveCodeBench (release_v3) | 612 / 612 | competitive programming, hidden tests | ours (TranslateGemma 27B, checked), output words in Italian |
| instructions | Multi-IF, turn 1 (shared ids) | 492 / 492 | verifiable format constraints | Llama 3.1 405B, checked by annotators |
| logic | Alice in Wonderland | 30 / 30 | robustness of basic relational reasoning | ours, native-read |
| logic | Zebra (generated) | 500 / 500 | logic grid puzzles, 2–6 houses × 2–6 attributes, same puzzle in both languages | generated from a native-reviewed config |
| chat | X-AlpacaEval | 805 / 805 | open-ended requests, judged pairwise | professional human translation |

The suite runs these. The data also holds the complete sets, off in the suite: `gpqa_main` (all of GPQA main, 448) and `multi_if_full` (493 Italian / 909 English, including the English-only items). Sources, papers, licences and caveats: [docs/benchmarks.md](docs/benchmarks.md) and `reports/{name}.md`. An overview with links: `notebooks/benchmarks.ipynb`.

## Install

Requirements: Linux, an NVIDIA GPU (24 GB fits a 4B model with 32k-token outputs), [uv](https://docs.astral.sh/uv/), and `bwrap` (bubblewrap: model-written code only ever runs inside it).

```bash
uv sync --extra gen        # vLLM 0.8.5 + torch 2.6 (cu124); plain `uv sync` is enough to build data and score
```

torch is pinned to CUDA 12.4 wheels for a 550.x driver; with a newer driver the vLLM/torch pins in `pyproject.toml` can be raised.

## Get the data

The benchmarks are on the private dataset [`minerva-post-training/ThinkBenchITA`](https://huggingface.co/datasets/minerva-post-training/ThinkBenchITA) (members of the organisation). Before using it, accept GPQA's terms on [`Idavidrein/gpqa`](https://huggingface.co/datasets/Idavidrein/gpqa) and [`ellamind/gpqa-multilingual`](https://huggingface.co/datasets/ellamind/gpqa-multilingual): its examples must never be shown in plain text online. Then:

```bash
uv run hf auth login
uv run python fetch_data.py        # data/{benchmark}/{lang}.jsonl, at the revision pinned in config/data.yaml
```

The dataset also loads on its own: `load_dataset("minerva-post-training/ThinkBenchITA", "aime25")`, one config per benchmark, splits `it` and `en`; its card describes the columns.

`data/` is git-ignored and stays unpublished: it contains GPQA.

Maintainers, to rebuild from the sources and publish:

```bash
uv run python fetch_data.py --sources DIR   # our raw files (translations as returned, Zebra puzzles), kept off the Hub
uv run python prepare.py                    # all sources at pinned revisions; or: prepare.py polymath gpqa
uv run python publish_data.py               # replaces the dataset's contents; then pin the printed commit in config/data.yaml
```

## Run a model

A model file says what changes between models; sampling (temperature 0.6, top-p 0.95, 32,768 new tokens; Olmo 3's) stays the suite's, so scores compare across models.

```yaml
# config/models/qwen3-4b-thinking-2507.yaml
model:
  path: Qwen/Qwen3-4B-Thinking-2507
  max_model_len: 40960
  tensor_parallel_size: 1
  chat_template_kwargs: {}
think_delims: ["<think>", "</think>"]
```

```bash
# everything enabled in config/eval.yaml, one model copy per GPU
uv run python run_eval.py --run qwen3-4b --model-config config/models/qwen3-4b-thinking-2507.yaml --gpus 0 1

# a quick check of the pipeline first (5 items per file, outputs cut at 2k tokens: the scores mean nothing)
uv run python run_eval.py --run smoke --model-config config/models/qwen3-4b-thinking-2507.yaml --limit 5 --max-tokens 2048

# some benchmarks or languages; re-score saved outputs without a GPU
uv run python run_eval.py --run qwen3-4b --model-config ... --benchmarks aime25 gpqa --langs it
uv run python run_eval.py --run qwen3-4b --stage score
```

- **A new model**: copy a file in `config/models/`, set `path`, `max_model_len` (prompt + 32k new tokens), `tensor_parallel_size` (GPUs per model copy), `chat_template_kwargs` (e.g. `{enable_thinking: true}`) and `think_delims`. `qwen3-8b.yaml` is the example of a model that needs two GPUs per copy (bf16, 24 GB cards).
- `--gpus` with more GPUs than `tensor_parallel_size` runs one process per group, each on every n-th item of every file, then merges the outputs; vLLM seeds each request, so the split does not change the samples. On one GPU, leave `--gpus` out.
- Generation stops at start-up if the think delimiters are neither in the model's chat template nor in its vocabulary.
- Outputs are saved as each prompt finishes, so `runs/{run}/` can be read while a run is going, and a stopped run resumes: the same command generates only the items still missing (`--overwrite` starts over). Rows are put back in item order when generation ends. On a shared GPU, pass `--gpu-memory-utilization`.
- `--no-thinking` saves only the final answer: the trace checks (format, loops, language, length) are computed from the full output at generation time and kept; the thinking text is not written. Smaller files, but no reading of the reasoning later.
- Which benchmarks run, their languages, samples per item (n=10 for code, n=32 for AIME and AIW) and breakdowns: `config/eval.yaml`.
- X-AlpacaEval, once a judge is chosen (`config/judge.yaml`): `xalpaca_reference.py --lang it` once, then `xalpaca_judge.py --run {run} --lang it`.

## Outputs

`runs/{run}/` (git-ignored):

| file | content |
|---|---|
| `summary.md` | one row per benchmark × language: pass@k, truncated, format ok, loops, trace ok, median thinking length, thinking in English, and notes |
| `report.md` | Italian vs English per benchmark, the thinking checks, and a few wrong and truncated outputs to read (`python -m src.run_report runs/{run}` rebuilds it) |
| `metrics.json` | everything in `summary.md`, plus the breakdowns |
| `{benchmark}/{lang}.jsonl` | one row per output: prompt, full completion, thinking, answer, token counts, finish reason, score, trace checks. Italian rows point to their English twin (`en_trace_id`) |

Trace checks (`src/trace_stats.py`, adapted from trace_criteria), per output:

- **format**: one thinking block, closed, non-empty, followed by a non-empty answer; not truncated; no lost bytes.
- **loops**: repeated 4-grams, a repeated paragraph (code left out: rewriting a function while checking it is not a loop), or an ending stuck on one short sequence; the summary also gives the share of truncated outputs that loop.
- **language** (Italian outputs): share of English words in the thinking, mostly-English paragraphs, language switches between paragraphs, and the language of the answer.
- **length**: thinking tokens and words; per item, the Italian/English ratio, flagged over ×2 or under ×0.5.
- **trace ok**: format ok, no loop, and no mostly-English paragraph.

## Layout

| path | content |
|---|---|
| `fetch_data.py`, `run_eval.py` | get the benchmarks, run a model |
| `prepare.py`, `publish_data.py` | maintainers: build the benchmarks from the sources, publish them (`docs/dataset_card.md`) |
| `config/eval.yaml`, `config/models/` | suite settings; one file per model |
| `src/loaders/` | one loader per benchmark; source revisions pinned in `src/loaders/__init__.py` |
| `src/scorers/` | `math_verify`, `mcq`, `exact_match`, `grid_match`, `code_exec` (sandboxed), `ifeval` (vendored Multi-IF checkers) |
| `src/italian.yaml` | every Italian instruction we wrote, with its English original (native-reviewed) |
| `src/generate.py`, `src/trace_stats.py`, `src/metrics.py`, `src/run_report.py` | generation, trace checks, metrics, report |
| `reports/{benchmark}.md`, `reports/issues/` | inspection report per benchmark; everything found wrong in a source and not edited |
| `zebra_generate.py`, `config/zebra/` | regenerate `zebra_gen` (in the generator's own environment; see the docstring) |
| `translation_export.py`, `config/translation/`, `docs/translation_handoff.md` | how the code benchmarks were translated |
| `xalpaca_reference.py`, `xalpaca_judge.py`, `config/judge.yaml` | X-AlpacaEval (judge pending) |
| `docs/decisions.md` | the working log: decisions, problems found in the sources, to-do |

## Unified format

One JSON object per line in `data/{benchmark}/{lang}.jsonl` (on the Hub, the same rows in Parquet with `answer` and `meta` as JSON text, so all benchmarks share one schema; `fetch_data.py` turns them back into these files):

| field | content |
|---|---|
| `id` | stable, identical across languages for parallel items |
| `lang` | `it` or `en` |
| `messages` | chat prompt |
| `answer` | gold answer (string, or a grid for Zebra); `null` for code, instruction following and judge tasks |
| `scorer` | `math_verify`, `mcq`, `code_exec`, `ifeval`, `judge_pairwise`, `grid_match`, `exact_match` |
| `meta` | source-specific: level, tests, instruction ids, `source_prompt` (the untouched source text), `template` |

Source text is never edited silently: repairs are logged in `reports/issues/` and the item's `meta`, with the original kept.

## Tests

```bash
uv run pytest     # scorers, sandbox, metrics, trace checks, and the data in data/ (after fetch_data.py or prepare.py)
```
