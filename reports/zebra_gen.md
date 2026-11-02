# Zebra (generated, parallel IT/EN) (`zebra_gen`)

- **Source:** generated with github.com/alexandrainst/zebra_puzzles at 9109b894 by zebra_generate.py; Italian config reviewed (config/zebra/it_case.yaml), English upstream en/houses
- **Paper:** Bruun & Smart, 2025, MultiZebraLogic (arXiv:2511.03553); sizes and classes from Lin et al., 2025, ZebraLogic (arXiv:2502.01100)
- **Licence:** generator Apache 2.0; the puzzles are ours
- **Scorer:** grid_match on the JSON dictionary (casa_X / house_X -> attributes, order inside a house ignored); cell accuracy also reported, and the off-list rate: answers with a value in none of the puzzle's lists (e.g. English words in an Italian answer)

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | 500 | 500 | 0 |
| en | 500 | 500 | 0 |

Scorer per item: `grid_match` 1000.

## ID alignment between Italian and English

- ids in both languages: **500**
- only in Italian: **0**
- only in English: **0**

## Missing or malformed items

None found.

## Notes and decisions

- Item-parallel: each puzzle is generated with the same seed in both languages, which gives the same solution and the same clues in the same order (the generator draws indices; the Italian config lists everything in the English order). zebra_generate.py asserts it for every puzzle.
- ZebraLogic's 25 sizes (houses 2-6 x categories 2-6), 20 puzzles per size (ZebraLogic has 40), no red herrings (as ZebraLogic). `size_class` is ZebraLogic's small/medium/large/xlarge by (houses!)^categories.
- Not ZebraLogic's puzzles, clue sentences or answer format, so scores are not comparable with the `zebra` benchmark; the IT/EN comparison is the point.
- Changes to the generator's behaviour, all in zebra_generate.py: per-puzzle seeds (0-499; 0-999 reserved for evaluation, training data must use seeds >= 1,000,000); value lists in the header in config order instead of alphabetical, so both languages list them identically; answer-format example with keys casa_X / house_X and the category names as placeholders.
- Answer format changed in both languages (2026-10-16): the generator's example ("Bevande_1" placeholders) made models answer with identifiers ("Bevande_soda", "romanzo_d_amore") and, in Italian, with English values; Qwen3-8B on 60 small puzzles scored 4% (it) and 35% (en) strictly but 67% and 99% leniently. Now keys casa_X / house_X, placeholders are the category names, and values must be written exactly as listed.
- Italian config: the upstream Preliminary config with 11 wording fixes and an imperative answer instruction, reviewed by a native speaker (reports/zebra_it_review.md).
- Generation is deterministic (checked: two runs give identical files); the files' sha256 are in config/zebra/manifest.json and checked on load.
- The model is asked for the generator's JSON answer only; the prompt has no reasoning field, unlike ZeroEval's.
