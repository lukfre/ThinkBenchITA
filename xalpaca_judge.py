"""Judge a run's X-AlpacaEval outputs against the reference outputs, AlpacaEval 2-style.

    uv run python xalpaca_judge.py --run qwen3-8b --lang it

Reads runs/{run}/xalpaca/{lang}.jsonl and data/xalpaca/reference.{lang}.jsonl, writes the
judgments back into the run file (`score`) and prints the raw and length-controlled win rates.
Only the model's final answer is shown to the judge, never its thinking. With n > 1 samples per
item, each sample is judged; the win rate is over samples.
"""

import argparse
import json

from src import judge
from src.schema import DATA_DIR, ROOT, read_jsonl, write_jsonl


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--lang", choices=["it", "en"], default="it")
    ap.add_argument("--config")
    args = ap.parse_args()

    config = judge.load_config(args.config)
    spec = config["judge"]
    client = judge.client_for(spec)
    path = ROOT / "runs" / args.run / "xalpaca" / f"{args.lang}.jsonl"
    rows = read_jsonl(path)
    reference_path = DATA_DIR / "xalpaca" / f"reference.{args.lang}.jsonl"
    if not reference_path.exists():
        raise SystemExit(f"{reference_path} not found: run xalpaca_reference.py --lang {args.lang} first")
    references = {r["id"]: r for r in read_jsonl(reference_path)}
    missing = sorted({r["prompt_id"] for r in rows} - set(references))
    if missing:
        raise SystemExit(f"{len(missing)} items have no reference output (e.g. {missing[:3]})")

    first = [judge.model_first(r["trace_id"], spec["seed"]) for r in rows]
    requests = []
    for row, model_is_first in zip(rows, first):
        reference = references[row["prompt_id"]]["output"]
        a, b = (row["answer"], reference) if model_is_first else (reference, row["answer"])
        requests.append(judge.judge_messages(args.lang, row["prompt"], a, b))
    replies = judge.map_parallel(lambda m: judge.judge_one(client, spec, m), requests, spec.get("concurrency", 8))

    generator = sorted({r["generator"] for r in references.values()})
    annotations = []
    for row, model_is_first, reply in zip(rows, first, replies):
        pref = judge.preference(judge.p_first(reply["top_logprobs"]), model_is_first)
        row["score"] = {
            "correct": None if pref is None else pref > 1.5,  # win; a tie (1.5) is not a win
            "preference": pref,  # AlpacaEval scale: 1 reference preferred .. 2 model preferred
            "model_first": model_is_first,
            "judge_text": reply["text"],
            "judge_top_logprobs": reply["top_logprobs"],
            "judge_model": spec["model"],
            "judge_prompt_hash": judge.prompt_hash(args.lang),
            "reference_model": generator,
        }
        if pref is not None:
            annotations.append({
                "instruction": row["prompt"], "output_1": references[row["prompt_id"]]["output"], "output_2": row["answer"],
                "generator_1": "reference", "generator_2": args.run, "preference": pref,
                "index": row["meta"]["source_id"] - 1,  # AlpacaEval instruction index
            })
    write_jsonl(path, rows)
    prefs = [a["preference"] for a in annotations]
    result = {
        "n": len(rows),
        "unparsed": len(rows) - len(prefs),
        "win_rate": 100 * sum(p - 1 for p in prefs) / len(prefs) if prefs else None,  # AlpacaEval: mean preference
        "judge_model": spec["model"],
        "judge_prompt_hash": judge.prompt_hash(args.lang),
        "reference_model": generator,
    }
    try:
        lc = judge.length_controlled(annotations)
        result["length_controlled_win_rate"] = lc["length_controlled_v1"]["win_rate"]  # AlpacaEval 2 headline
        result["length_controlled_noreg_win_rate"] = lc["length_controlled_noreg"]["win_rate"]
        result["lc_standard_error"] = lc["length_controlled_v1"]["standard_error"]
        result["lc_note"] = ("v1 is regularised towards AlpacaEval's English length-gamed baselines; noreg is not. "
                             + ("Italian: both use English-derived instruction difficulties and are not validated yet." if args.lang == "it" else ""))
    except ImportError:
        result["length_controlled_win_rate"] = None
        result["lc_note"] = "install the judge extra (uv sync --extra judge) to compute it"
    (path.parent / f"judge.{args.lang}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nrun `uv run python run_eval.py --run {args.run} --stage score --benchmarks xalpaca` to refresh summary.md")


if __name__ == "__main__":
    main()
