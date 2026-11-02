"""Generate the parallel Italian/English Zebra set (`zebra_gen`) with the MultiZebraLogic generator.

Runs inside the generator's own environment, not this project's:

    git clone https://github.com/alexandrainst/zebra_puzzles .cache/zebra_puzzles
    git -C .cache/zebra_puzzles checkout 9109b894
    (cd .cache/zebra_puzzles && uv sync)
    .cache/zebra_puzzles/.venv/bin/python -I zebra_generate.py

What this adds to the generator (whose CLI takes no seed):
- One seed per puzzle, the same in both languages. The generator's random choices pick indices
  (categories, values, clue types), and the Italian config lists everything in the same order as
  the English one, so equal seeds give the same puzzle in both languages: same solution, same
  clues in the same order.
- Value lists in the puzzle header follow the config order (the same in both languages) instead of
  being sorted alphabetically per language. Neither order depends on the solution.
- The answer-format example lists the category names under keys casa_X / house_X
  ({"casa_1": ["Nazionalità", "Bevande"], ...}) instead of the generator's "Nazionalità_1"
  placeholders, which models copied as identifiers ("Bevande_soda", "romanzo_d_amore"). The gold
  answers use the same keys. The format paragraph itself is edited in both configs.
- Seeds 0-999 are reserved for evaluation: training data must be generated from seeds >= 1_000_000.

Writes .cache/zebra_gen/{it,en}.jsonl and config/zebra/manifest.json (sha256 of both files, generator
commit, config hashes, settings). The loader refuses files that do not match the manifest.
"""

import argparse
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent
COMMIT = "9109b89422ddebedba59d689903ddffd9daca2c3"
EVAL_SEEDS = range(0, 1000)
SIZES = [(h, c) for h in range(2, 7) for c in range(2, 7)]  # ZebraLogic: houses 2-6 x categories 2-6
ANSWER_KEY = {"it": "casa", "en": "house"}


def solution_template(key: str):
    """Answer-format example: one list of category names per house, as in the header."""
    from zebra_puzzles.zebra_utils import capitalize

    def build(n_objects, chosen_categories):
        example = {f"{key}_{i}": [capitalize(str(c)) for c in chosen_categories] for i in range(1, n_objects + 1)}
        return json.dumps(example, indent=4, ensure_ascii=False)

    return build


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_language(path: Path) -> dict:
    from zebra_puzzles.zebra_utils import build_case_to_index, validate_language_config

    c = yaml.safe_load(path.read_text(encoding="utf-8"))
    validate_language_config(
        attribute_cases=list(c["attribute_cases"]),
        red_herring_attribute_cases=list(c["red_herring_attribute_cases"]),
        clue_cases_dict=c["clue_cases_dict"],
        red_herring_cases_dict=c["red_herring_cases_dict"],
        attributes=c["attributes"],
        red_herring_attributes=c["red_herring_attributes"],
    )
    # the same arguments, with the same defaults, as src/scripts/build_dataset.py
    return dict(
        attributes=c["attributes"],
        clues_dict=c["clues_dict"],
        clue_cases_dict=c["clue_cases_dict"],
        prompt_templates=c["prompt_templates"],
        prompt_and=c["prompt_and"],
        prompt_replacements=c["prompt_replacements"],
        red_herring_clues_dict=c["red_herring_clues_dict"],
        red_herring_attributes=c["red_herring_attributes"],
        red_herring_facts=c["red_herring_facts"],
        red_herring_cases_dict=c["red_herring_cases_dict"],
        case_to_index=build_case_to_index(list(c["attribute_cases"])),
        red_herring_case_to_index=build_case_to_index(list(c["red_herring_attribute_cases"])),
        attribute_subject_cases=dict(c.get("attribute_subject_cases", {})),
        same_object_templates=dict(c.get("same_object_templates", {})),
        not_same_object_templates=dict(c.get("not_same_object_templates", {})),
        red_herring_subject_cases=dict(c.get("red_herring_subject_cases", {})),
        same_herring_templates=dict(c.get("same_herring_templates", {})),
        double_herring_templates=dict(c.get("double_herring_templates", {})),
        prompt_comma=c.get("prompt_comma", ", "),
        prompt_and_spacing=c.get("prompt_and_spacing", True),
        prompt_full_stop=c.get("prompt_full_stop", "."),
        prompt_colon=c.get("prompt_colon", ": "),
    )


def config_order(attributes: dict) -> dict[str, tuple[int, int]]:
    """Value -> (category index, value index) in the config."""
    order = {}
    for ci, values in enumerate(attributes.values()):
        for vi, value in enumerate(values):
            assert value not in order, f"value {value!r} appears in two categories"
            order[value] = (ci, vi)
    return order


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=ROOT / ".cache/zebra_puzzles")
    ap.add_argument("--out", type=Path, default=ROOT / ".cache/zebra_gen")
    ap.add_argument("--per-size", type=int, default=20)
    ap.add_argument("--n-red-herrings", type=int, default=0)
    ap.add_argument("--seed-start", type=int, default=0)
    args = ap.parse_args()

    head = subprocess.run(["git", "-C", str(args.repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != COMMIT:
        sys.exit(f"generator at {head}, expected {COMMIT}")
    n_total = args.per_size * len(SIZES)
    seeds = range(args.seed_start, args.seed_start + n_total)
    if not (seeds.start in EVAL_SEEDS and seeds.stop - 1 in EVAL_SEEDS):
        sys.exit("evaluation sets must use seeds 0-999")

    sys.path.insert(0, str(args.repo / "src"))
    from zebra_puzzles.puzzle_creation import build_pipeline, prompt_completion

    base = yaml.safe_load((args.repo / "config/config.yaml").read_text(encoding="utf-8"))
    configs = {
        "it": ROOT / "config/zebra/it_case.yaml",  # reviewed copy, see reports/zebra_it_review.md
        "en": ROOT / "config/zebra/en_houses.yaml",  # upstream en/houses (a "Finished" language), format paragraph edited
    }
    languages = {lang: load_language(path) for lang, path in configs.items()}
    orders = {lang: config_order(kw["attributes"]) for lang, kw in languages.items()}

    args.out.mkdir(parents=True, exist_ok=True)
    rows = {lang: [] for lang in languages}
    seed = iter(seeds)
    for houses, categories in SIZES:
        for k in range(args.per_size):
            s = next(seed)
            for lang, kw in languages.items():
                # header lists in config order; `sorted` is used only there in prompt_completion
                prompt_completion.sorted = lambda xs, _o=orders[lang]: sorted(xs, key=lambda v: _o[v])
                prompt_completion.create_solution_template = solution_template(ANSWER_KEY[lang])
                random.seed(s)
                np.random.seed(s)
                prompt, solution, red_herrings, clue_types = build_pipeline.run_pipeline(
                    n_objects=houses,
                    n_attributes=categories,
                    n_red_herring_clues=args.n_red_herrings,
                    clue_weights=base["clue_weights"],
                    red_herring_clue_weights=base["red_herring_clue_weights"],
                    **kw,
                )
                rows[lang].append(
                    {
                        "id": f"zebra_gen-{houses}x{categories}-{k:02d}",
                        "seed": s,
                        "houses": houses,
                        "categories": categories,
                        "prompt": prompt,
                        "solution": {k.replace("object", ANSWER_KEY[lang]): v for k, v in json.loads(solution).items()},
                        # language-neutral solution: (category index, value index) in the config, per house
                        "cells": [[list(orders[lang][v]) for v in vals] for vals in json.loads(solution).values()],
                        "clue_types": clue_types.split(", ") if clue_types else [],
                        "red_herring_indices": red_herrings,
                    }
                )
            # the two languages must be the same puzzle: same clue types, same cells in config terms
            it, en = rows["it"][-1], rows["en"][-1]
            assert it["clue_types"] == en["clue_types"], it["id"]
            assert it["cells"] == en["cells"], it["id"]
        print(f"{houses}x{categories} done", flush=True)

    files = {}
    for lang, items in rows.items():
        path = args.out / f"{lang}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for row in items:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        files[lang] = {"file": rel(path), "rows": len(items), "sha256": sha256(path)}

    manifest = {
        "generator": "github.com/alexandrainst/zebra_puzzles",
        "commit": COMMIT,
        "configs": {lang: {"path": rel(p), "sha256": sha256(p)} for lang, p in configs.items()},
        "sizes": [f"{h}x{c}" for h, c in SIZES],
        "per_size": args.per_size,
        "n_red_herrings": args.n_red_herrings,
        "seeds": [seeds.start, seeds.stop - 1],
        "header_order": "config",
        "answer_keys": ANSWER_KEY,
        "files": files,
    }
    manifest_path = ROOT / "config/zebra/manifest.json" if args.out == ROOT / ".cache/zebra_gen" else args.out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(files, indent=2))


if __name__ == "__main__":
    main()
