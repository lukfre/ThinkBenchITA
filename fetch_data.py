"""Get the benchmarks: download the built data from the private Hugging Face dataset (config/data.yaml).

    uv run python fetch_data.py                  # data/{benchmark}/{lang}.jsonl, ready for run_eval.py
    uv run python fetch_data.py --sources DIR    # maintainers: copy our raw files from DIR, then prepare.py

The download is the published version of data/ (publish_data.py), at the revision pinned in
config/data.yaml, written back byte for byte as prepare.py builds it.

--sources: rebuilding from the sources with prepare.py needs our own raw files, which are not on the
Hub: the code-benchmark translations as the pipeline returned them and the generated Zebra puzzles
(DIR laid out as translation/{benchmark}.jsonl and zebra_gen/{lang}.jsonl). Each file is checked
against the sha256 in its tracked manifest; a file that differs is refused.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "data.yaml"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_sha256(manifest_path: str, to: str) -> str:
    manifest = json.loads((ROOT / manifest_path).read_text(encoding="utf-8"))
    if "benchmarks" in manifest:  # the translation pipeline's manifest: one entry per benchmark
        return manifest["benchmarks"][Path(to).stem]["sha256"]
    return next(entry["sha256"] for entry in manifest["files"].values() if entry["file"] == to)  # zebra_generate.py's


def from_record(record: dict) -> dict:
    """Inverse of publish_data.to_record: the row as prepare.py writes it."""
    answer = record["answer"]
    if answer is not None and record["scorer"] == "grid_match":
        answer = json.loads(answer)
    return {"id": record["id"], "lang": record["lang"], "messages": record["messages"], "answer": answer,
            "scorer": record["scorer"], "meta": json.loads(record["meta"])}


def download(config: dict) -> None:
    import pyarrow.parquet as pq
    from huggingface_hub import snapshot_download

    if not config.get("revision"):
        sys.exit("config/data.yaml: no revision pinned")
    local = Path(snapshot_download(config["hf_repo"], repo_type="dataset", revision=config["revision"], allow_patterns=["*.parquet"]))
    n = 0
    for name in config["benchmarks"]:
        for path in sorted((local / name).glob("*.parquet")):
            rows = [from_record(r) for r in pq.read_table(path).to_pylist()]
            dest = ROOT / "data" / name / f"{path.stem}.jsonl"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
            n += 1
    print(f"{n} files in data/ ({config['hf_repo']}@{config['revision'][:8]})")


def copy_sources(config: dict, source: Path) -> None:
    failed = []
    for name, spec in config["sources"].items():
        got, dest = source / name, ROOT / spec["to"]
        if not got.exists() or sha256(got) != expected_sha256(spec["manifest"], spec["to"]):
            failed.append(name)
            print(f"REFUSED {name}: missing or sha256 differs from {spec['manifest']}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(got, dest)
        print(f"ok      {name} -> {spec['to']}")
    if failed:
        sys.exit(f"{len(failed)} file(s) refused")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", type=Path, metavar="DIR", help="copy our raw files from DIR (to rebuild with prepare.py)")
    args = ap.parse_args()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    if args.sources:
        copy_sources(config, args.sources)
    else:
        download(config)


if __name__ == "__main__":
    main()
