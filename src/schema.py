"""Unified item format and the small I/O helpers shared by loaders and scorers.

One JSONL file per benchmark x language: data/{benchmark}/{lang}.jsonl, one
`Item` per line. Source text is never edited: the loader copies it into
`messages` through a fixed template (see prompts.py) and keeps the untouched
source prompt in `meta.source_prompt`. Anything that looks wrong in a source
goes to the benchmark's issue log (`Issues`), never into the data.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REPORT_DIR = ROOT / "reports"

# The five scorers of docs/original_spec.md, plus two this build had to add:
# `grid_match` (Zebra: "exact grid match") and `exact_match` (the 20 INVALSI
# fill-the-gap items, which are neither MCQ nor a single math expression).
SCORERS = {"math_verify", "mcq", "code_exec", "ifeval", "judge_pairwise", "grid_match", "exact_match"}
LANGS = ("it", "en")


@dataclass
class Item:
    id: str
    lang: str
    messages: list[dict] | None  # None = placeholder waiting for translation
    answer: Any
    scorer: str
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.lang not in LANGS:
            raise ValueError(f"{self.id}: lang {self.lang!r}")
        if self.scorer not in SCORERS:
            raise ValueError(f"{self.id}: scorer {self.scorer!r}")

    @property
    def pending(self) -> bool:
        """Placeholder row (same id as its English twin, no prompt yet)."""
        return self.messages is None


def user(content: str) -> list[dict]:
    return [{"role": "user", "content": content}]


def placeholder(en: Item, **meta) -> Item:
    """Italian row with the id of `en` and no text, for the translation pipeline.

    `meta.translate` names the English fields to translate; everything else in
    the English item (answer, tests) is reused unchanged once the row is filled.
    """
    return Item(
        id=en.id,
        lang="it",
        messages=None,
        answer=en.answer,
        scorer=en.scorer,
        meta={"pending_translation": True, **meta},
    )


def write_jsonl(path: Path, rows: Iterable[dict | Item]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(asdict(row) if isinstance(row, Item) else row, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_items(benchmark: str, lang: str, data_dir: Path = DATA_DIR) -> list[Item]:
    return [Item(**row) for row in read_jsonl(data_dir / benchmark / f"{lang}.jsonl")]


class Issues:
    """Per-benchmark log of things found in the source that we did NOT fix."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, kind: str, detail: str, id: str | None = None, lang: str | None = None):
        self.rows.append({"id": id, "lang": lang, "kind": kind, "detail": detail})


@dataclass
class Built:
    """What a loader returns."""

    items: dict[str, list[Item]]  # lang -> items
    issues: Issues
    info: dict  # source, revision, licence, paper, scorer, notes, decisions
