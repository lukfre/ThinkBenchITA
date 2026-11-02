"""Build data/{benchmark}/{lang}.jsonl, the inspection reports and the side-by-side samples.

    uv run python prepare.py                 # every benchmark
    uv run python prepare.py polymath gpqa   # some
"""

import sys

from src.loaders import LOADERS
from src.report import write_report, write_sample
from src.schema import DATA_DIR, REPORT_DIR, write_jsonl

# Gated sources: nothing derived from their content may land in a tracked file.
PRIVATE = {"gpqa", "gpqa_main", "zebra"}


def main(names: list[str]) -> None:
    unknown = [n for n in names if n not in LOADERS]
    if unknown:
        sys.exit(f"unknown benchmark(s) {unknown}; available: {sorted(LOADERS)}")
    summary = []
    for name in names or sorted(LOADERS):
        built = LOADERS[name]()
        for lang, items in built.items.items():
            path = DATA_DIR / name / f"{lang}.jsonl"
            if items:
                write_jsonl(path, items)
            elif path.exists():
                path.unlink()  # a source that became unavailable must not leave stale data behind
        private = name in PRIVATE
        row = write_report(name, built, REPORT_DIR, DATA_DIR / name if private else None)
        n_sample = write_sample(name, built, (DATA_DIR / name) if private else (REPORT_DIR / "samples"))
        summary.append(row)
        print(f"{name:16s} {row['counts']}  aligned={row['both']}  issues={row['issues']}  sample={n_sample}")
    if not names:
        lines = ["# Benchmarks built", "", "| benchmark | it | en | ids in both | pending (it) | logged issues | report |", "|---|---|---|---|---|---|---|"]
        for r in summary:
            lines.append(
                f"| {r['title']} | {r['counts'].get('it', '–')} | {r['counts'].get('en', '–')} | {r['both']} | "
                f"{r['pending'].get('it', 0)} | {r['issues']} | [{r['name']}.md]({r['name']}.md) |"
            )
        (REPORT_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
