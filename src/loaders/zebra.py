"""Zebra puzzles.

`zebra`       English ZebraLogic (allenai/ZebraLogicBench-private, grid_mode;
              the public repo has the solutions blanked out). Gated.
`zebra_gen`   Italian and English puzzles generated with the MultiZebraLogic
              generator (alexandrainst/zebra_puzzles), same seed per puzzle in
              both languages, so item-parallel. See zebra_generate.py and
              reports/zebra_generator.md.
"""

import hashlib
import json
import math
from pathlib import Path

import pandas as pd

from ..schema import Built, Issues, Item, user
from . import SourceUnavailable, hf_file, register, source

REPO = "allenai/ZebraLogicBench-private"
ROOT = Path(__file__).resolve().parents[2]
GEN_MANIFEST = ROOT / "config/zebra/manifest.json"
# ZeroEval's grid-mode prompt, as used by OLMES (oe_eval/tasks/oe_eval_tasks/zebralogic.py)
GRID_PROMPT = (Path(__file__).parent / "zebra_grid_prompt.txt").read_text(encoding="utf-8")
EASY_SIZES = ["2*2", "2*3", "2*4", "2*5", "2*6", "3*2", "3*3"]


@register("zebra")
def build() -> Built:
    issues = Issues()
    en = []
    try:
        df = pd.read_parquet(hf_file(REPO, "grid_mode/test-00000-of-00001.parquet"))
        for row in df.to_dict("records"):
            header = [str(h) for h in row["solution"]["header"]]
            rows = [[str(c) for c in r] for r in row["solution"]["rows"]]
            if header[0] != "House":
                issues.add("unexpected_header", str(header), row["id"], "en")
            template = {"reasoning": "___", "solution": {f"House {i + 1}": {c: "___" for c in header[1:]} for i in range(len(rows))}}
            prompt = GRID_PROMPT.replace("{puzzle}", row["puzzle"]).replace("{json_template}", json.dumps(template, indent=4))
            grid = {f"House {i + 1}": dict(zip(header[1:], r[1:])) for i, r in enumerate(rows)}
            if any(v == "___" for house in grid.values() for v in house.values()):
                issues.add("blank_solution", "solution cells are blanked", row["id"], "en")
            en.append(
                Item(
                    id=row["id"],
                    lang="en",
                    messages=user(prompt),
                    answer=grid,
                    scorer="grid_match",
                    meta={
                        "size": row["size"],
                        "difficulty": "easy" if row["size"] in EASY_SIZES else "hard",
                        "format": "zebralogic",
                        "source_prompt": row["puzzle"],
                        "template": "zeroeval-grid",
                    },
                )
            )
    except SourceUnavailable as e:
        issues.add("source_unavailable", str(e), lang="en")
    return Built(
        {"en": en},
        issues,
        {
            "name": "ZebraLogic",
            "source": source(REPO) + " (grid_mode)",
            "paper": "Lin et al., 2025, ZebraLogic: On the Scaling Limits of LLMs for Logical Reasoning (arXiv:2502.01100)",
            "licence": "not declared; the repo with solutions is gated to keep them out of training data. Do not publish.",
            "scorer": "grid_match: every cell of the predicted grid equals the gold grid (cell accuracy is also reported)",
            "notes": [
                "English only for now. The Italian side is to be generated with MultiZebraLogic: see reports/zebra_generator.md.",
                "The public allenai/ZebraLogicBench has every solution cell replaced by `___`; gold grids are only in the gated -private repo.",
                "Prompt is ZeroEval's one-shot grid-mode prompt, the one OLMES (Olmo 3) uses; `easy`/`hard` follows ZeroEval's size split.",
                "`grid_match` is not one of the five scorers of the instructions; it was added for this benchmark.",
                "Checked 2026-10-15: 1000 puzzles, 40 per size from 2*2 to 6*6; ids unique; no blank gold cell; every prompt's JSON template asks for exactly the houses and columns of its gold grid; every gold value appears in its puzzle; every gold scores 100% against itself. The answer parser takes the last valid JSON object, so it handles a code block, trailing text, braces inside the reasoning string, or a bare solution object.",
            ],
        },
    )


def size_class(houses: int, categories: int) -> str:
    """ZebraLogic's difficulty classes, by the number of possible grids (houses!)^categories."""
    log10 = categories * math.log10(math.factorial(houses))
    return "small" if log10 < 3 else "medium" if log10 < 6 else "large" if log10 < 10 else "xlarge"


@register("zebra_gen")
def build_gen() -> Built:
    issues = Issues()
    items = {"it": [], "en": []}
    if not GEN_MANIFEST.exists():
        issues.add("source_unavailable", "config/zebra/manifest.json missing: run zebra_generate.py")
    else:
        manifest = json.loads(GEN_MANIFEST.read_text(encoding="utf-8"))
        for lang, entry in manifest["files"].items():
            path = ROOT / entry["file"]
            if not path.exists():
                issues.add("source_unavailable", f"{entry['file']} missing: run zebra_generate.py (see its docstring)", lang=lang)
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"{path} does not match config/zebra/manifest.json: regenerate with zebra_generate.py")
            for row in map(json.loads, path.read_text(encoding="utf-8").splitlines()):
                h, c = row["houses"], row["categories"]
                grid = {k: [str(x) for x in v] for k, v in row["solution"].items()}
                key = manifest["answer_keys"][lang]
                if sorted(grid) != sorted(f"{key}_{i}" for i in range(1, h + 1)) or any(len(v) != c for v in grid.values()):
                    issues.add("bad_solution_shape", f"{h}x{c}", row["id"], lang)
                missing = [v for vals in grid.values() for v in vals if v not in row["prompt"]]
                if missing:
                    issues.add("gold_value_not_in_prompt", str(missing), row["id"], lang)
                items[lang].append(
                    Item(
                        id=row["id"],  # same id = same puzzle in both languages
                        lang=lang,
                        messages=user(row["prompt"]),
                        answer=grid,
                        scorer="grid_match",
                        meta={
                            "size": f"{h}x{c}",
                            "houses": h,
                            "categories": c,
                            "size_class": size_class(h, c),
                            "format": "multizebra",
                            "seed": row["seed"],
                            "cells": row["cells"],  # language-neutral gold: equal across languages
                            "clue_types": row["clue_types"],
                            "n_red_herrings": manifest["n_red_herrings"],
                            "template": "multizebra-generator",
                        },
                    )
                )
        ids = {lang: [i.id for i in v] for lang, v in items.items()}
        if all(ids.values()) and ids["it"] != ids["en"]:
            issues.add("ids_not_parallel", "Italian and English ids differ")
    return Built(
        items,
        issues,
        {
            "name": "Zebra (generated, parallel IT/EN)",
            "source": "generated with github.com/alexandrainst/zebra_puzzles at 9109b894 by zebra_generate.py; Italian config reviewed (config/zebra/it_case.yaml), English upstream en/houses",
            "paper": "Bruun & Smart, 2025, MultiZebraLogic (arXiv:2511.03553); sizes and classes from Lin et al., 2025, ZebraLogic (arXiv:2502.01100)",
            "licence": "generator MIT (alexandrainst/zebra_puzzles LICENSE); the puzzles are ours",
            "scorer": "grid_match on the JSON dictionary (casa_X / house_X -> attributes, order inside a house ignored); cell accuracy also reported, and the off-list rate: answers with a value in none of the puzzle's lists (e.g. English words in an Italian answer)",
            "notes": [
                "Item-parallel: each puzzle is generated with the same seed in both languages, which gives the same solution and the same clues in the same order (the generator draws indices; the Italian config lists everything in the English order). zebra_generate.py asserts it for every puzzle.",
                "ZebraLogic's 25 sizes (houses 2-6 x categories 2-6), 20 puzzles per size (ZebraLogic has 40), no red herrings (as ZebraLogic). `size_class` is ZebraLogic's small/medium/large/xlarge by (houses!)^categories.",
                "Not ZebraLogic's puzzles, clue sentences or answer format, so scores are not comparable with the `zebra` benchmark; the IT/EN comparison is the point.",
                "Changes to the generator's behaviour, all in zebra_generate.py: per-puzzle seeds (0-499; 0-999 reserved for evaluation, training data must use seeds >= 1,000,000); value lists in the header in config order instead of alphabetical, so both languages list them identically; answer-format example with keys casa_X / house_X and the category names as placeholders.",
                "Answer format changed in both languages (2026-10-16): the generator's example (\"Bevande_1\" placeholders) made models answer with identifiers (\"Bevande_soda\", \"romanzo_d_amore\") and, in Italian, with English values; Qwen3-8B on 60 small puzzles scored 4% (it) and 35% (en) strictly but 67% and 99% leniently. Now keys casa_X / house_X, placeholders are the category names, and values must be written exactly as listed.",
                "Italian config: the upstream Preliminary config with 11 wording fixes and an imperative answer instruction, reviewed by a native speaker (reports/zebra_it_review.md).",
                "Generation is deterministic (checked: two runs give identical files); the files' sha256 are in config/zebra/manifest.json and checked on load.",
                "The model is asked for the generator's JSON answer only; the prompt has no reasoning field, unlike ZeroEval's.",
            ],
        },
    )
