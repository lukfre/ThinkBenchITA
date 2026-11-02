# Multi-IF, turn 1: which instruction types depend on language, and what the checkers do with Italian

Code inspected: `facebookresearch/Multi-IF` at commit `1cdb53ed` (`ifeval.py`, `metrics.py`), vendored unchanged in `src/scorers/vendor/multi_if_ifeval.py`. Data: `facebook/Multi-IF`, `multiIF_20241018.csv`, turn 1 (493 Italian prompts, 909 English). The behaviours below were checked by running the vendored checkers on Italian strings.

## Summary

- The Multi-IF authors **removed from the non-English data the instruction types that only make sense in English**. Italian turn 1 has 18 instruction types; six English ones never occur: `change_case:english_capital`, `change_case:english_lowercase`, `change_case:capital_word_frequency`, `keywords:letter_frequency`, `language:response_language`, `detectable_content:postscript`. So capitalisation and letter-frequency checks, two of the four cases the task asked about, **do not exist in the Italian set**.
- The checker code has **no Italian-specific path**. It special-cases Thai, Hindi, Chinese and Japanese (detected with `langdetect` on the response) and sends everything else, Italian included, through the English code.
- Instruction arguments are translated: keywords, forbidden words, end phrases, first words and section names are Italian strings in the Italian rows.
- For Italian, the English path is exact for most types and approximate for two: **sentence counts** (English Punkt model) and **word counts** (elisions count as two words). Keyword checks are literal, which is stricter in an inflected language.

The full Italian and English sets therefore differ in instruction mix: a raw IT-vs-EN accuracy gap over all items mixes a language effect with a task-mix effect. The clean comparison is on the **492 ids present in both languages**: on those, the instruction ids are identical in the two languages (checked on all 492), and the English-only instruction types occur only in the 417 English prompts that have no Italian counterpart. `run_eval.py` reports this shared-id accuracy next to the overall one. For a finer view, `score.follow_strict` and `score.instruction_id_list` are stored per output.

## Instruction types in turn 1

| instruction | it | en | language-dependent? | behaviour on Italian text |
|---|---|---|---|---|
| `punctuation:no_comma` | 65 | 110 | no | regex for `,` |
| `length_constraints:number_words` | 55 | 84 | **yes** | `\w+` tokens. `L'aria` counts as 2 words, `dell'acqua` as 2. Measured on the Italian prompts of Multi-IF and X-AlpacaEval: +1.5% over a whitespace count (+0.4% on the English Multi-IF prompts). Small, but it matters at the threshold: it favours "at least N" and penalises "less than N". |
| `startend:quotation` | 53 | 74 | **yes** | accepts `"…"`, `“…”`, `「…」`. Italian caporali `«…»` are **rejected**. |
| `detectable_format:number_highlighted_sections` | 52 | 79 | no | markdown `*…*` |
| `length_constraints:number_sentences` | 52 | 77 | **yes** | NLTK Punkt, **English** model. Italian abbreviations it does not know split sentences: `Il sig. Rossi …` is cut after `sig.`. Over-counts on formal text; the Italian Punkt model would not. |
| `keywords:forbidden_words` | 50 | 89 | **yes** | `\bword\b`, case-insensitive, Unicode-aware (accents are fine: `città`, `perché` match). Literal: forbidding `cibo` does not forbid `cibi`. |
| `detectable_format:title` | 45 | 65 | no | `<<title>>` |
| `keywords:existence` | 34 | 63 | **yes** | Multi-IF: case-insensitive **substring** (`casa` found in "casale"). **Changed here to whole words** (see below). Still literal: `casa` is not found in "le case", and the Italian keywords are often inflected forms (`correlati`, `sperimentando`), so the model must use that exact form. |
| `combination:two_responses` | 33 | 43 | no | split on `******` |
| `combination:repeat_prompt` | 33 | 69 | no | response must start with the (Italian) prompt, case-insensitive |
| `detectable_content:number_placeholders` | 31 | 47 | no | `[...]` |
| `length_constraints:number_paragraphs` | 31 | 45 | no | split on `***` |
| `detectable_format:number_bullet_lists` | 28 | 46 | no | `* ` / `- ` lines |
| `keywords:frequency` | 27 | 74 | **yes** | Multi-IF counts substring matches: "use 'il' at most once" counted the 'il' in possib**il**e, sim**il**e, ut**il**e (multiif-2716-1/-8 were nearly impossible). **Changed here to whole words.** |
| `detectable_format:json_format` | 21 | 27 | no | parses as JSON |
| `startend:end_checker` | 21 | 49 | mild | response must end with the Italian phrase, case-insensitive, exact punctuation |
| `detectable_format:multiple_sections` | 15 | 19 | mild | splitter word is in the kwargs (`Sezione` / `SEZIONE`), matched literally and case-sensitively |
| `length_constraints:nth_paragraph_first_word` | 15 | 21 | **yes** | first whitespace token, lower-cased, cut at the first of `. , ? ! ' "`. An elided first word (`L'idea`) is cut to `l`, so it can never match a target like `l'idea`; accents are kept. |
| `change_case:english_capital` / `english_lowercase` | 0 | 44 / 67 | English only | require `langdetect == "en"`; an all-caps Italian answer fails by construction. Not in the Italian data. |
| `change_case:capital_word_frequency` | 0 | 43 | – | not in the Italian data |
| `keywords:letter_frequency` | 0 | 54 | – | not in the Italian data. (It counts exact characters: `è` is not `e`.) |
| `language:response_language` | 0 | 48 | – | not in the Italian data |
| `detectable_content:postscript` | 0 | 43 | – | not in the Italian data (`P.S.` / `P.P.S` markers) |

Counts are instruction occurrences; an Italian prompt carries 1 (345 prompts), 2 (128) or 3 (20) instructions.

## Other things that affect Italian scores

- **`langdetect` on the response decides the code path** for word and sentence counts. On short or all-caps Italian it can return another language (measured: "Sì." → `vi`, "CIAO A TUTTI, COME STATE OGGI?" → `pt`). None of the wrong guesses observed lands on Thai/Hindi/Chinese/Japanese, the only ones with a different path, so the practical effect on Italian is nil; it is also non-deterministic unless seeded, which matters only for those borderline cases.
- **Thinking must be stripped before checking.** Every checker reads the whole string; a `<think>` block would break `quotation`, `repeat_prompt`, `end_checker` and inflate counts. The harness passes the final answer only.
- **Strict vs loose.** Strict checks the answer as is. Loose also tries it without the first line, the last line, both, and with `*` removed, and passes if any variant passes. `correct` is strict prompt-level accuracy (all instructions of the prompt followed); loose and instruction-level accuracy are reported next to it.
- 73 English turn-1 prompts mention "English" in the instruction text (the `change_case:english_*` and language instructions); 2 Italian prompts (`multiif-3329-6`, `multiif-3329-14`) ask for "paragrafi di inglese semplice", a literal translation of "plain English": an answer in English is a defensible reading of those two, so exclude them from Italian language-compliance metrics. They are in the issue log, not edited.

## Changes made to the checkers and to the data (2026-10-15)

**Keyword checks match whole words, in both languages.** `keywords:existence` and `keywords:frequency` now match a keyword only as a whole word or phrase: Unicode-aware, with punctuation and elided articles as boundaries ("l'impegno" contains "impegno"), and the keyword taken literally rather than as a regex. Multi-IF searched substrings, so "il" was found in "possibile" and "the" in "there". This concerns 61 Italian and 137 English instructions: on those, our scores are no longer identical to Multi-IF's reference code. The change is marked in `src/scorers/vendor/multi_if_ifeval.py` and covered by tests.

**Five Italian prompts repaired** (not translations of the checker, so the checker could not be satisfied by following the prompt):
- `multiif-1922-5`, `-1922-9`, `-288-9`: the "repeat the request word for word first" instruction had been dropped; restored with our translation of the English sentence.
- `multiif-3245-3`: the sentence "no commas, at least 2 placeholders in [square brackets]" had been dropped; restored, translated by us.
- `multiif-2662-10`: the prompt asked for the keyword 'occuparsi' while the checker tests 'impegna' (English "engages"); the prompt now asks for 'impegna'.
Each repaired item has `meta.repaired=true` and its original prompt in `meta.source_prompt_original`.

**Outer quotes removed from 127 Italian prompts.** 127 of the 493 Italian prompts (no English one) were wrapped whole in a pair of double quotes, a translation artefact: the prompt read as quoted text, and the `combination:repeat_prompt` checker, which expects the request without quotes, could fail if the model repeated them. Only the outer pair is removed; inner quotes stay. These items have `meta.outer_quotes_removed=true` and the original prompt in `meta.source_prompt_original`.

## Decisions

- The checkers are used **as Multi-IF ships them**, including the English sentence model and the `«»` rejection, with one exception: keyword checks match whole words (above). Other code change: the Thai tokenizer import is optional.
- The approximations above are not corrected. If an Italian-aware variant is wanted (Italian Punkt model, whitespace-based word count, `«»` accepted), it should be added as a second, clearly named metric, not as a replacement.
