# Zebra in Italian: state of the MultiZebraLogic generator

Inspected: `github.com/alexandrainst/zebra_puzzles` at commit `9109b894` (2026-08-07), paper arXiv:2511.03553, Apache 2.0.

## Finding: Italian is already there, as a "Preliminary" language

Nothing has to be written to add Italian. The repo ships `config/language/it/case.yaml` (houses theme, `language=it/case`), and the authors already publish puzzles generated from it on the Hub: `alexandrainst/zebra_puzzles`, configs `dataset_it_case_2x3_5rh` and `dataset_it_case_4x5_5rh` (128 train / 128 val / 1024 test each).

The README lists Italian under **Preliminary versions**, next to the *Finished* ones (Danish, Dutch, English, German, …). Preliminary means the config was drafted with the repo's `/add-language` agent skill and **has not been reviewed by a native speaker**. The Italian file says so itself: "Uncertain forms (flagged for native speaker review): gassosa (soda)".

## How the generator works (what a language needs)

No LLM is involved. A puzzle is a random solution grid, plus clues drawn from 14 clue types (found_at, next_to, between, …) and filtered by a constraint solver until the solution is unique, plus optional red-herring clues that must not change it. All text comes from one YAML file per language/theme:

| section | content | Italian status |
|---|---|---|
| `attributes` | 7 categories, each value in 3 grammatical forms (`nom`, `is`, `is_not`) | present: 11 nationalities, 7 values in each of the other 6 categories |
| `red_herring_attributes`, `red_herring_facts` | distractor attributes and facts | present (16 + 10) |
| `clues_dict`, `clue_cases_dict` | one sentence template per clue type and the form each slot takes | all 14 present |
| `red_herring_clues_dict` | 8 distractor templates | present |
| `prompt_templates` | puzzle text, question, answer-format instruction | present, in Italian |
| `prompt_replacements` | find-and-replace rules; here the article contractions (`a il` → `al`, `di lo` → `dello`, …) | present |

With 7 categories of at least 7 values, the Italian config can generate up to 7 houses × 7 attributes, so it covers the ZebraLogic size range (2×2 to 6×6).

## What I checked

- Generated 6×6 Italian puzzles from the config at that commit: `uv run src/scripts/build_dataset.py language=it/case n_objects=6 n_attributes=6 n_puzzles=2 n_red_herring_clues=5`. It runs out of the box, about 3 s per 6×6 puzzle on this machine.
- Read the generated puzzles and the published 4×5 test set. The Italian is grammatical in what I read: contractions are right ("accanto al proprietario", "a destra di chi ama le mele"), clue templates are natural ("Tra il panettiere e chi beve gassosa c'è una casa").

Points for the native review (none of these is fixed here):

1. `gassosa` for "soda": flagged upstream; "bibita gassata" is the generic term, "gassosa" is a specific drink.
2. `fragola` and `fragola di bosco` are both values of *Frutta preferita*. They are distinct values; English has the same pair (strawberry / wild strawberry), so this is the generator's design, not an Italian trap (corrected in `zebra_it_review.md`).
3. Masculine forms throughout ("il proprietario", "l'infermiere", "il commesso"): a deliberate choice of the config, to check against how we want the benchmark to read.
4. The format instruction is formal ("Si prega di inviare la risposta come dizionario JSON"); fine, but decide whether it should match the register of our other Italian prompts.
5. `Nazionalità` values are country names ("Francia") while clues use demonyms ("il francese"): the solver of the puzzle must map one to the other. This is how every language of the generator works, English included.

## What is needed to get an Italian Zebra set for our suite

1. **Native review of `it/case.yaml`**, following the repo's `REVIEWING_LANGUAGES.md` (generate 4×5 puzzles with 5 red herrings, read, edit the config, regenerate). Half a day of work; ideally contributed upstream so Italian moves to "Finished".
2. **Decide the sizes and the number of red herrings.** The published sets are 2×3 and 4×5 with 5 red herrings. ZebraLogic spans 2×2 to 6×6 with no red herrings. To mirror ZebraLogic, generate each size with `n_red_herring_clues=0`; `n_puzzles`, `n_objects`, `n_attributes` are command-line overrides, and generation is fast (seconds per puzzle up to 6×6).
3. **Accept that it is not a translation of ZebraLogic.** Puzzles are generated independently per language: there are no item ids shared with the English ZebraLogic set, the clue inventory differs, and the answer format differs (a JSON dictionary `object_X → [attributes]`, against ZebraLogic's `House N → {column: value}` grid). For a controlled IT/EN comparison, generate the English side with the same generator (`en/houses`, a *Finished* language) at the same sizes: the two sets are then matched in distribution, though still not item-parallel.
4. **Seeds**: `build_dataset.py` does not take a seed in `config.yaml`; fix the generated files (commit hash + generated data) rather than relying on regeneration.

## What is in this repo now (2026-10-16)

- `zebra` (English ZebraLogic, `allenai/ZebraLogicBench-private`): the standard English benchmark, gated.
- `zebra_gen`: 500 Italian + 500 English puzzles generated by `zebra_generate.py` with the reviewed Italian config (`reports/zebra_it_review.md`) and upstream `en/houses`. Point 3 above no longer holds: seeding each puzzle identically in both languages gives the **same puzzle in both languages** (the generator's random draws pick indices, and the Italian config lists categories and values in the English order). Checked on every puzzle at generation; `meta.cells` holds the language-neutral solution. Point 4 too: generation is deterministic, and the files are pinned by sha256 in `config/zebra/manifest.json`.
- `multizebra` (the published 2×3/4×5 sets) has been removed.
