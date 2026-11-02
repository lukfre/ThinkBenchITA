# ZebraLogic (`zebra`)

- **Source:** allenai/ZebraLogicBench-private@9f39ef49 (grid_mode)
- **Paper:** Lin et al., 2025, ZebraLogic: On the Scaling Limits of LLMs for Logical Reasoning (arXiv:2502.01100)
- **Licence:** not declared; the repo with solutions is gated to keep them out of training data. Do not publish.
- **Scorer:** grid_match: every cell of the predicted grid equals the gold grid (cell accuracy is also reported)

## Items

| lang | items | ready | pending translation |
|---|---|---|---|
| it | – (no Italian side) | | |
| en | 1000 | 1000 | 0 |

Scorer per item: `grid_match` 1000.

## ID alignment between Italian and English

- single-language benchmark: nothing to align.

## Missing or malformed items

None found.

## Notes and decisions

- English only for now. The Italian side is to be generated with MultiZebraLogic: see reports/zebra_generator.md.
- The public allenai/ZebraLogicBench has every solution cell replaced by `___`; gold grids are only in the gated -private repo.
- Prompt is ZeroEval's one-shot grid-mode prompt, the one OLMES (Olmo 3) uses; `easy`/`hard` follows ZeroEval's size split.
- `grid_match` is not one of the five scorers of the instructions; it was added for this benchmark.
- Checked 2026-10-15: 1000 puzzles, 40 per size from 2*2 to 6*6; ids unique; no blank gold cell; every prompt's JSON template asks for exactly the houses and columns of its gold grid; every gold value appears in its puzzle; every gold scores 100% against itself. The answer parser takes the last valid JSON object, so it handles a code block, trailing text, braces inside the reasoning string, or a bare solution object.
