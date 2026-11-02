# Zebra in Italian: review of the generator's Italian config

Config reviewed: `config/language/it/case.yaml` of `alexandrainst/zebra_puzzles` at commit `9109b894`, against the reviewed English config (`en/houses.yaml`), following the repo's `REVIEWING_LANGUAGES.md`.

Sample read: 95 Italian puzzles with 5 red herrings (5 at 4×5, 30 each at 3×4, 5×5, 6×6), 1938 clues covering all 14 clue types and all 8 red-herring types, plus 2×2 and 6×6 puzzles without red herrings. Clone and samples are in `.cache/zebra_puzzles/data/it_case/` (git-ignored).

**Status (2026-10-16): native read done. Accepted: C1–C2, N1–N9, R1 (imperative: "Fornisci la risposta come dizionario JSON."). R2: generic masculine kept. Applied in `config/zebra/it_case.yaml` (upstream copy: `config/zebra/it_case.upstream.yaml`); used by `zebra_generate.py`.**

## What is fine

- Grammar of the clue templates: every type reads correctly in what was generated (examples below).
- Article contractions: no wrong form in 1938 clues ("accanto al", "a destra del", "a sinistra dell'…"). The 13 sentences an automatic scan flagged are all "tra l'…", which is correct ("tra" does not contract).
- The negated red herring `cactus` ("non ha un cactus") is not an Italian bug: English has the same ("does not own a cactus").
- `fragola` / `fragola di bosco` in the same category: English has the same pair (strawberry / wild strawberry), so it is the generator's design, not an Italian trap. (This corrects the earlier note in `zebra_generator.md`.)

## Proposed edits (for the native read)

Each row: current form → proposed form, and why. Priorities as in `REVIEWING_LANGUAGES.md`: correctness, unambiguity, naturalness, consistency with English.

### Correctness

| # | where | current | proposed | why |
|---|---|---|---|---|
| C1 | Nazionalità, Isole Fær Øer | il faroense / è faroense | il faroese / è faroese | the usual Italian demonym is "faroese" (lingua faroese); "faroense" is rare |
| C2 | red herring `matematica` | nom "il laureato in matematica", is "ha una laurea magistrale in matematica" | nom "chi ha una laurea magistrale in matematica" | the two forms say different things (any degree vs master's); English has master's in both |

### Naturalness

| # | where | current | proposed | why |
|---|---|---|---|---|
| N1 | Bevande, gassosa | chi beve gassosa | chi beve bibite gassate (value `bibita gassata`) | flagged upstream: "gassosa" is a specific lemon soda; English is generic "soda" |
| N2 | Nazionalità, Paesi Bassi | il neerlandese | l'olandese | "neerlandese" is correct but formal; "olandese" is the everyday demonym |
| N3 | Hobby, uncinetto | chi fa uncinetto | chi lavora all'uncinetto | "fa uncinetto" without article is unusual ("fa l'uncinetto" / "lavora all'uncinetto") |
| N4 | Hobby, giochi da tavolo | chi gioca ai giochi da tavolo | chi gioca a giochi da tavolo | avoids the repeated "gioca ai giochi" |
| N5 | red herring `vela` | chi naviga spesso a vela | chi va spesso in barca a vela | more idiomatic |
| N6 | red herring `mango` | chi pensa che il secondo miglior frutto sia il mango | chi pensa che il mango sia il secondo frutto migliore | word order |
| N7 | red herring `animale_vecchio` | il proprietario di un animale vecchio per la sua specie | chi ha un animale anziano per la sua specie | "anziano" is the usual word for an animal |
| N8 | red herring `tatuaggio` | il tatuato | chi ha un tatuaggio | "il tatuato" reads as slang; matches "the person with a tattoo" |
| N9 | facts `case`, `automobili` | tutte le case nella strada…; ci sono molte automobili nella strada | tutte le case della strada…; ci sono molte automobili in strada | prepositions |

### Register and gender (decisions, not errors)

| # | where | current | options |
|---|---|---|---|
| R1 | answer-format instruction | "Si prega di inviare la risposta come dizionario JSON." (impersonal, formal) | keep, or "Fornisci la risposta come dizionario JSON." to match our other Italian prompts, which use the imperative ("Scrivi la risposta finale…") |
| R2 | masculine forms | il proprietario di…, il panettiere, il poliziotto, il commesso, l'infermiere, il britannico… | keep the generic masculine (the config's stated choice), or switch descriptions to "chi" forms where possible (chi ha un gatto, chi fa il panettiere). The second is longer and changes every clue; the first is standard in Italian puzzles |

## Examples per clue type (current config)

| type | example |
|---|---|
| found_at / not_at | L'infermiere abita nella casa numero 2. / L'insegnante non abita nella casa numero 4. |
| next_to / not_next_to | Il programmatore abita accanto al proprietario di una lumaca. / L'italiano non abita accanto a chi gioca a calcio, e sono persone diverse. |
| just_left_of / just_right_of | Lo spagnolo abita immediatamente a sinistra di chi legge horror. / L'infermiere abita immediatamente a destra del proprietario di una lumaca. |
| left_of / right_of | Chi beve caffè abita a sinistra di chi ama le arance. / Lo spagnolo abita a destra del proprietario di un gatto. |
| same_object / not_same_object | Il danese ha una lumaca. / Il proprietario di un cane non legge fantasy. |
| between / not_between | Il ministro abita tra il francese e il proprietario di un gatto. / Il francese non abita tra il norvegese e chi gioca a pallamano, e sono tre persone diverse. |
| one_between / multiple_between | Tra il poliziotto e il proprietario di una lumaca c'è una casa. / Tra il proprietario di un gatto e chi beve tè ci sono 2 case. |
| red herrings | Il danese porta gli occhiali. / Chi dipinge sa che alcune case hanno una porta verde. / Chi legge saggistica e chi ama la fisica sono buoni amici. / Il cetriolo è una bacca. |

## Generation plan (proposal)

- **Sizes**: mirror ZebraLogic, houses 2–6 × attributes 2–6 (25 sizes), 40 puzzles per size, 1000 per language, **no red herrings** (ZebraLogic has none). Grouped by ZebraLogic's size classes for reporting.
- **English**: the same sizes and settings from `en/houses` (a reviewed language), so the two sides match in distribution. They are not item-parallel.
- **Pinning**: puzzle sampling is unseeded (the `seed=42` in the code is the solver's only), so we keep our edited Italian config in this repo, record the generator commit, and freeze the generated files under `data/`. Generation time: 10 puzzles take 0.6 s at 2×2 and 28 s at 6×6.

## Answer format (2026-10-16, both languages)

The generator's format example used placeholders like `"Bevande_1"`, `"Frutta_preferita_1"`. Models copied their shape: category prefixes and underscores (`"Bevande_soda"`, `"romanzo_d_amore"`) and, in Italian, English values. Qwen3-8B on 60 small puzzles × 2 samples scored 4.2% (it) and 35.0% (en) strictly, against 66.7% and 99.2% when those were normalised away.

Changed in both configs (`config/zebra/it_case.yaml`, `config/zebra/en_houses.yaml`) and in `zebra_generate.py`:

```text
Fornisci la risposta come dizionario JSON. Ogni chiave deve essere casa_X, dove X è il numero della casa. Ogni valore deve essere l'elenco degli attributi della persona che abita nella casa numero X, uno per categoria, nell'ordine delle categorie, scritti esattamente come negli elenchi sopra.

Di seguito è riportato un esempio del formato della risposta:

{"casa_1": ["Nazionalità", "Professioni", "Bevande"], "casa_2": ["Nazionalità", "Professioni", "Bevande"]}
```

English: keys `house_X`, "written exactly as in the lists above". After the change: 65.0% (it) and 100.0% (en). 40 of the 42 wrong Italian answers contain values that are not in the Italian lists (English words, or the model's own translations); the scorer now reports this as the off-list rate.
