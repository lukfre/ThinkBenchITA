"""Maintainers: publish the built benchmarks (data/) to the private Hugging Face dataset.

    uv run python publish_data.py --dry-run DIR    # write the files to DIR only, to inspect them
    uv run python publish_data.py                  # replace the dataset's contents with the current data/

Layout: README.md (the card, docs/dataset_card.md with one config per benchmark) and
{benchmark}/{it,en}.parquet. Every file has the same fixed schema, so loading does not depend on
type inference or on the `datasets` version:

    id, lang, scorer: string
    messages: list of {role, content}
    answer: string or null (the gold answer; for grid_match, the grid as JSON text)
    meta: string (JSON text: tests, source prompt, provenance, ...)

fetch_data.py turns these files back into data/{benchmark}/{lang}.jsonl, byte for byte.
After publishing, set `revision` in config/data.yaml to the printed commit.
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "data.yaml"
SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("lang", pa.string()),
        ("messages", pa.list_(pa.struct([("role", pa.string()), ("content", pa.string())]))),
        ("scorer", pa.string()),
        ("answer", pa.string()),
        ("meta", pa.string()),
    ]
)


def to_record(row: dict) -> dict:
    answer = row["answer"]
    if answer is not None and not isinstance(answer, str):
        answer = json.dumps(answer, ensure_ascii=False)
    return {"id": row["id"], "lang": row["lang"], "messages": row["messages"], "scorer": row["scorer"], "answer": answer,
            "meta": json.dumps(row["meta"], ensure_ascii=False)}


def build(out: Path, benchmarks: list[str]) -> list[tuple[str, list[str]]]:
    configs = []
    for name in benchmarks:
        langs = []
        for lang in ("it", "en"):
            src = ROOT / "data" / name / f"{lang}.jsonl"
            if not src.exists():
                continue
            rows = [json.loads(line) for line in src.read_text(encoding="utf-8").split("\n") if line]  # not splitlines(): U+2028 occurs in strings
            if any(r["messages"] is None for r in rows):
                sys.exit(f"{src}: rows waiting for translation; only complete files are published")
            (out / name).mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pylist([to_record(r) for r in rows], schema=SCHEMA), out / name / f"{lang}.parquet")
            langs.append(lang)
        if not langs:
            sys.exit(f"data/{name}: nothing built; run prepare.py first")
        configs.append((name, langs))
    header = {"license": "other", "language": ["it", "en"], "pretty_name": "ThinkBenchITA",
              "configs": [{"config_name": n, "data_files": [{"split": l, "path": f"{n}/{l}.parquet"} for l in ls]} for n, ls in configs]}
    card = (ROOT / "docs" / "dataset_card.md").read_text(encoding="utf-8")
    (out / "README.md").write_text("---\n" + yaml.safe_dump(header, sort_keys=False, allow_unicode=True) + "---\n\n" + card, encoding="utf-8")
    return configs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", type=Path, metavar="DIR", help="write the files to DIR and stop")
    args = ap.parse_args()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if args.dry_run:
        configs = build(args.dry_run, config["benchmarks"])
        print(f"{len(configs)} configs in {args.dry_run}")
        return

    from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

    api, repo = HfApi(), config["hf_repo"]
    if not api.repo_info(repo, repo_type="dataset").private:
        sys.exit(f"{repo} is not private: it holds GPQA, whose terms forbid showing its examples publicly")
    with tempfile.TemporaryDirectory() as tmp:
        build(Path(tmp), config["benchmarks"])
        new = sorted(str(p.relative_to(tmp)) for p in Path(tmp).rglob("*") if p.is_file())
        old = [f for f in api.list_repo_files(repo, repo_type="dataset") if f != ".gitattributes" and f not in new]
        ops = [CommitOperationDelete(f) for f in old] + [CommitOperationAdd(f, str(Path(tmp) / f)) for f in new]
        commit = api.create_commit(repo, ops, repo_type="dataset", commit_message="Publish data/ (publish_data.py)")
    print(f"published {len(new)} files, removed {len(old)}; commit {commit.oid}: set it as `revision` in config/data.yaml")


if __name__ == "__main__":
    main()
