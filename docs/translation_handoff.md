# Handoff: Italian translation of the code benchmarks

For the agent running the translation pipeline on Cineca. The pipeline itself is yours; this note says what to translate, what to send back, and which choices are open.

## Context

ThinkBenchITA (then called evaluation-bench) is an Italian/English benchmark suite for reasoning models. Every benchmark has an Italian and an English file with the same item ids, so the two languages can be compared item by item. Three code benchmarks have no Italian version, and their Italian files hold only placeholders:

| benchmark | items | what gets translated | source |
|---|---|---|---|
| HumanEval+ | 164 | the docstring prose of a Python function stub | `evalplus/humanevalplus` |
| MBPP+ | 378 | one or two task sentences in a docstring | `evalplus/mbppplus` |
| LiveCodeBench (release_v3) | 612 | competitive-programming statements (LeetCode, AtCoder, Codeforces), about 850k characters | `livecodebench/code_generation_lite` |

The model under test reads the Italian statement and writes a program, which is then run against the original tests. The tests are not translated. Anything the program has to match exactly must therefore survive the translation unchanged: names, signatures, sample inputs and outputs, and quoted values. Only the prose changes.

## Input

`data/_translation/export/{humaneval,mbppplus,livecodebench}.jsonl` and `manifest.json`, produced by `translation_export.py` in the repo. The manifest has row counts and sha256 hashes, so you can check the copy you received. One row per item:

```json
{"id": "lcb-1873_A", "benchmark": "livecodebench", "text": "... Output \"⟦OUT_1⟧\" if it is possible, and \"⟦OUT_2⟧\" otherwise. ...", "rule": "Translate the problem statement ... Keep unchanged: ...", "placeholders": {"⟦OUT_1⟧": "YES", "⟦OUT_2⟧": "NO"}}
```

- `text`: the English to translate, exactly as the model will see it once translated.
- `rule`: what to keep unchanged, per benchmark (also repeated below). Treat it as part of the translation instructions.
- `placeholders`: LiveCodeBench only, 59 rows. The words a program must print (Yes/No in 51 problems, plus First/Second, Bat/Glove, Takahashi/Aoki/Draw, Unreachable, undecidable, infinite, san, Alice/Bob) are replaced by `⟦OUT_n⟧`. **Copy every placeholder through unchanged, as many times as it occurs.** We put back the chosen words afterwards and map the test outputs to them. Words of the same kind that are not masked (e.g. the `"yEs", "yes"` variants listed in lcb-1873_A) count as quoted values: keep them.

## What to translate, what to keep

**HumanEval+.** The text is a Python stub: imports, signature, docstring, sometimes helper functions.
- Translate only the prose of the docstring.
- Keep byte for byte: code outside the docstring, the signature, identifiers, doctest lines (`>>> f(...)` and the line with its result), example calls and their results, and every quoted value (strings the function must accept or return).
- Keep the indentation and the docstring's quote style.
- Example: `""" Input to this function is a string containing multiple groups of nested parentheses. ...` → the prose in Italian, then `>>> separate_paren_groups('( ) (( )) (( )( ))')` and `['()', '(())', '(()())']` unchanged.

**MBPP+.** The text is a docstring holding the task sentence and one `assert` line.
- Translate the sentence.
- Keep the `assert` line, the names and the quoted values unchanged.
- Example: `Write a python function to identify non-prime numbers.` → `Scrivi una funzione Python che identifichi i numeri non primi.`

**LiveCodeBench.**
- Translate the statement, section headings included (Input, Output, Constraints, Sample Input/Output, Example, Explanation, Note).
- Keep unchanged:
  - sample inputs and outputs;
  - code;
  - identifiers and variable names;
  - LaTeX and formulas (`$1 \leq t \leq 10^4$`, `$\texttt{abc}$`), and constraints written in symbols;
  - every quoted value;
  - person names (Takahashi, Aoki, Slavic);
  - the placeholders.
- Example: `print ⟦OUT_1⟧; otherwise, print ⟦OUT_2⟧.` → `stampa ⟦OUT_1⟧; altrimenti, stampa ⟦OUT_2⟧.`

Don't localise numbers: `0.5` stays `0.5` and `10^9` stays `10^9`. Inputs and outputs use the English notation, and the statement has to describe them as they are.

## Choices to make (record each in the run manifest)

1. **Model.** Use the strongest multilingual model available to you, with greedy decoding (or temperature 0). Record the exact model name and revision. We report the translation as "LLM-translated (model X)".
2. **Whole text or prose only.**
   - For MBPP+ and LiveCodeBench, translate the whole text in one call. LaTeX and samples are interleaved with the prose, and segmenting them is error-prone.
   - For HumanEval+, two options: the whole stub plus the rule, then the checks below; or extract the docstring, translate it, and splice it back. The second can't damage the code, so prefer it if your pipeline makes it easy.
3. **Section headings in LiveCodeBench.**
   - "Input"/"Output" are common in Italian programming contests as they are. The Italian Olympiad in Informatics uses "Dati di input"/"Dati di output".
   - Pick one rendering per heading and use it in all 612 problems. Record the mapping.
4. **Register.** Statements that address the reader use the informal "tu" (as our Italian instructions do: "Scrivi…", "Leggi…"). Third-person narration stays third person.
5. **Comments inside code** (rare, HumanEval+): keep them in English. They are code.
6. **Failures.** If a row fails a check below after one retry, don't fix it by hand. Return it with `"status": "failed"` and the reason, and we review those rows ourselves.

## Checks before returning

They're cheap and automatic. Run all of them per row:
- every input id is returned exactly once;
- each placeholder appears as many times as in the English `text`;
- **HumanEval+:** the code with docstrings removed is identical (compare `ast.dump` of the parsed stub with docstrings stripped), and every `>>>` line and the line after it are unchanged;
- **MBPP+:** the `assert` line is unchanged;
- **LiveCodeBench:**
  - every `$...$` segment of the English occurs in the Italian;
  - every sample block (the text between "Sample Input/Output n" and the next heading) is unchanged;
  - every double-quoted string is unchanged;
- no English sentence is left untranslated: for example, flag rows where more than 30% of the prose words are common English words.

## Output

`data/_translation/returned/{benchmark}.jsonl`, one row per input row:

```json
{"id": "lcb-1873_A", "text_it": "...", "status": "ok", "checks_failed": [], "notes": ""}
```

Add `returned/manifest.json` with:
- the model and its revision;
- the full prompt template;
- the decoding parameters;
- your pipeline's commit;
- the date;
- the heading mapping (choice 3);
- per benchmark: rows, failed rows, and the sha256 of each returned file.

Copy the folder back to the machine with the repo, into the same path.

## What happens afterwards (our side, for your information)

- A fill step, not written yet, reads the returned files and builds the Italian prompts:
  - `prompts.evalplus_prompt('it', ...)` for HumanEval+ and MBPP+;
  - `prompts.lcb_messages('it', ...)` for LiveCodeBench, whose system message and format instructions are already in Italian.
- It re-runs the checks above and refuses rows that fail them.
- The 59 LiveCodeBench problems with placeholders get their output words translated by hand (e.g. Yes/No → Sì/No), and the expected test outputs are mapped to the same words.
- A native speaker reads a sample.

## Do not

- Publish the inputs or outputs anywhere public.
- Change ids, tests, or anything outside `text`.
- Translate GPQA or any other benchmark. Only these three are in scope.
