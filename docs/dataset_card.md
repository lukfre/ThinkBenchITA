# ThinkBenchITA

**Private: do not share outside minerva-post-training, and do not copy examples anywhere public. It contains GPQA (see Terms).**

Benchmarks for reasoning models in Italian, with the parallel English side: one config per benchmark, one split per language (`it`, `en`), and the same item ids in both. To run models on it, use the ThinkBenchITA code (`fetch_data.py` downloads this dataset; `run_eval.py` runs and scores a model).

```python
from datasets import load_dataset
import json

aime = load_dataset("minerva-post-training/ThinkBenchITA", "aime25")   # aime["it"], aime["en"]
row = aime["it"][0]
row["messages"]            # the prompt, as chat messages
row["answer"]              # the gold answer
json.loads(row["meta"])    # tests, source text, provenance, ...
```

## Benchmarks

| config | it / en | what it tests | Italian side |
|---|---|---|---|
| polymath | 500 / 500 (the suite uses medium + high: 222) | competition-level math word problems | GPT-4o, edited by professional translators |
| mclm_math100 | 99 / 99 | high-school competition math (MATH-500) | GPT-4o |
| mclm_aime2024 | 30 / 30 | AIME 2024 | GPT-4o |
| aime25 | 30 / 30 | AIME 2025 | LLM, checked by hand by its authors |
| invalsi_mate | 420 / – (the suite uses 397) | Italian national school math tests, grades 2–13 | native Italian |
| gpqa | 197 / 197 | GPQA Diamond: graduate-level biology, physics, chemistry (one of Diamond's 198 has its gold answer twice and is left out) | Gemini 3.1 Pro |
| gpqa_main | 448 / 448 | all of GPQA main (meta.is_diamond; meta.default=false on the 2 items with a duplicated gold) | Gemini 3.1 Pro |
| humaneval | 164 / 164 (the suite uses 163: /32's test is broken) | Python functions from a docstring | ours (TranslateGemma 27B, every row checked) |
| mbppplus | 378 / 378 | basic Python tasks | ours (TranslateGemma 27B, every row checked) |
| livecodebench | 612 / 612 | competitive programming | ours (TranslateGemma 27B, every row checked); output words in Italian |
| multi_if | 492 / 492 | verifiable format constraints, the ids in both languages | Llama 3.1 405B, checked by annotators |
| multi_if_full | 493 / 909 | every item, including the English-only ones (meta.default marks the shared ids) | Llama 3.1 405B, checked by annotators |
| aiw | 30 / 30 | basic relational reasoning ("Alice has N brothers…") | ours, native-read |
| zebra_gen | 500 / 500 | logic grid puzzles, the same puzzle in both languages | generated from a native-reviewed config |
| xalpaca | 805 / 805 | open-ended requests, judged pairwise | professional human translation |

Which items a run uses, and how many samples per item: `config/eval.yaml` of the code.

## Columns

Every config has the same columns:

| column | content |
|---|---|
| `id` | item id, the same in both languages |
| `lang` | `it` or `en` |
| `messages` | the prompt as chat messages (`role`, `content`) |
| `scorer` | how the answer is scored: `math_verify`, `mcq`, `exact_match`, `grid_match`, `code_exec`, `ifeval`, `judge_pairwise` |
| `answer` | the gold answer as a string; for `grid_match` (zebra_gen) the solution grid as JSON text; null where the scorer has no single answer (code tests, instruction checkers, judge) |
| `meta` | JSON text, specific to each benchmark: tests, the untouched source prompt, difficulty, provenance of the translation, repairs |

Not included: LiveCodeBench's private tests (the scorer reads them from `livecodebench/code_generation_lite`), ZebraLogic (gated to keep its solutions private) and the mHumanEval-Expert alternative (off in the suite).

## Terms

- **GPQA** (`gpqa`, `gpqa_main`): its sources (`Idavidrein/gpqa`, `ellamind/gpqa-multilingual`) are gated with *"You agree to NOT reveal examples from this dataset in plain text or images online, to reduce the risk of leakage into foundation model training corpora."* Accept those terms on the two source pages before using this config. Every row keeps the GPQA canary string.
- **Zebra** (`zebra_gen`): seeds 0–999 of the generator are reserved for evaluation; training data must use seeds from 1,000,000.
- Licences of the sources are listed in the code (`docs/benchmarks.md`); several are non-commercial (`aime25`, `multi_if`, `xalpaca`), and PolyMath, INVALSI and the LiveCodeBench statements are to be checked before any public release.
