"""Reference outputs for X-AlpacaEval.

    uv run python xalpaca_reference.py --lang en      # AlpacaEval 2's official GPT-4 Turbo outputs (no API)
    uv run python xalpaca_reference.py --lang it      # generated with the reference model in config/judge.yaml

Writes data/xalpaca/reference.{lang}.jsonl. References are generated once and reused by every
evaluation run: changing them changes what a "win" means.
"""

import argparse
import json

from src import judge
from src.schema import DATA_DIR, read_jsonl, write_jsonl

ALPACA_REPO, ALPACA_REV = "tatsu-lab/alpaca_eval", "2edc6fad8be6b14ea7230aabfd08188da6b8b814"


def official_english(items: list[dict]) -> list[dict]:
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(ALPACA_REPO, "alpaca_eval_gpt4_baseline.json", repo_type="dataset", revision=ALPACA_REV)
    baseline = json.load(open(path, encoding="utf-8"))
    rows = []
    for item in items:
        ref = baseline[item["meta"]["source_id"] - 1]  # X-AlpacaEval id n = AlpacaEval index n-1 (checked: 805/805)
        assert " ".join(ref["instruction"].split()) == " ".join(item["messages"][0]["content"].split()), item["id"]
        rows.append({"id": item["id"], "lang": "en", "output": ref["output"], "generator": ref["generator"], "source": f"{ALPACA_REPO}@{ALPACA_REV[:8]}"})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["it", "en"], default="it")
    ap.add_argument("--config")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    out = DATA_DIR / "xalpaca" / f"reference.{args.lang}.jsonl"
    if out.exists() and not args.overwrite:
        raise SystemExit(f"{out} exists; references are meant to be fixed. Pass --overwrite to replace them.")
    config = judge.load_config(args.config)
    items = read_jsonl(DATA_DIR / "xalpaca" / f"{args.lang}.jsonl")[: args.limit]
    if args.lang == "en" and config["reference"].get("en_official", True):
        rows = official_english(items)
    else:
        spec = config["reference"]
        client = judge.client_for(spec)
        outputs = judge.map_parallel(lambda item: judge.chat(client, spec, item["messages"]), items, spec.get("concurrency", 8))
        rows = [{"id": i["id"], "lang": args.lang, "output": o, "generator": spec["model"], "temperature": spec["temperature"], "max_tokens": spec["max_tokens"]} for i, o in zip(items, outputs)]
    write_jsonl(out, rows)
    empty = sum(not r["output"].strip() for r in rows)
    print(f"wrote {len(rows)} references to {out}" + (f" ({empty} EMPTY: check them before judging)" if empty else ""))


if __name__ == "__main__":
    main()
