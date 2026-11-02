"""Generate with vLLM and score.

    uv run python run_eval.py --run qwen3-8b                       # everything in config/eval.yaml
    uv run python run_eval.py --run qwen3-8b --benchmarks polymath humaneval --langs it
    uv run python run_eval.py --run qwen3-8b --stage score         # re-score saved outputs, no GPU
    uv run python run_eval.py --run smoke --model HuggingFaceTB/SmolLM2-1.7B-Instruct --limit 8 --max-tokens 512

Outputs, under runs/{run}/:
  {benchmark}/{lang}.jsonl   one row per item x sample: prompt, thinking, answer, tokens, score.
                             The rows follow trace_criteria's input schema (--dataset native).
  metrics.json, summary.md   pass@1 / pass@k per benchmark x language.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from src import metrics
from src.schema import DATA_DIR, ROOT, read_jsonl, write_jsonl
from src.scorers import code_exec, score
from src.run_report import write_run_report
from src.trace_stats import trace_stats

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # the sandbox forks after the tokenizer has been used

DOMAINS = {
    "polymath": "math", "mclm_math100": "math", "mclm_aime2024": "math", "aime25": "math", "invalsi_mate": "math",
    "gpqa": "science", "gpqa_main": "science", "zebra": "logic", "zebra_gen": "logic", "humaneval": "code", "humaneval_mhe": "code", "aiw": "logic", "mbppplus": "code",
    "livecodebench": "code", "multi_if": "if", "multi_if_full": "if", "xalpaca": "chat",
}  # fmt: skip


def select(benchmark: str, lang: str, spec: dict, limit: int | None) -> list[dict]:
    path = DATA_DIR / benchmark / f"{lang}.jsonl"
    if not path.exists():
        return []
    items = [i for i in read_jsonl(path) if i["messages"] is not None]
    for key, value in (spec.get("filter") or {}).items():
        items = [i for i in items if i["meta"].get(key) == value]
    return items[:limit] if limit else items


def generate(reader, run: str, jobs: list[tuple], sampling: dict, out_dir: Path, drop_thinking: str | None) -> None:
    """Generate every (benchmark, lang, items, en_ids) job as one vLLM batch, so a file's slowest
    trace does not leave the GPUs idle (each request keeps its own seed: the outputs do not depend
    on the grouping). Each item's rows are appended to its file as soon as it finishes, so a stopped
    run keeps what is done and resumes from there."""
    sampling = dict(sampling)
    n = sampling.pop("n")
    flat = [(job, item) for job in jobs for item in job[2]]
    files = {}
    try:
        for index, samples in reader.stream([item["messages"] for _, item in flat], n=n, **sampling):
            (benchmark, lang, _, en_ids), item = flat[index]
            rows = rows_for(run, benchmark, lang, [item], [samples], en_ids)
            if drop_thinking:
                for row in rows:
                    drop_thinking_text(row, drop_thinking)
            if (benchmark, lang) not in files:
                path = out_dir / benchmark / f"{lang}.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                files[benchmark, lang] = open(path, "a", encoding="utf-8")
            f = files[benchmark, lang]
            f.write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            f.flush()
    finally:
        for f in files.values():
            f.close()


def drop_thinking_text(row: dict, delims: list[str]) -> None:
    """--no-thinking: the trace checks need the full text, so they are computed now; then only
    the final answer is kept."""
    row["trace"] = trace_stats(row, delims)
    row["thinking"] = row["completion"] = None


def done_ids(path: Path, n: int) -> set[str]:
    """Items whose n samples are all in the file (an item's samples are written together)."""
    if not path.exists():
        return set()
    counts = {}
    for row in read_jsonl(path):
        counts[row["prompt_id"]] = counts.get(row["prompt_id"], 0) + 1
    return {i for i, c in counts.items() if c >= n}


def sort_file(path: Path, items: list[dict]) -> None:
    """Rows in item order (they are appended in completion order)."""
    order = {item["id"]: k for k, item in enumerate(items)}
    rows = read_jsonl(path)
    rows.sort(key=lambda r: (order.get(r["prompt_id"], len(order)), r["sample_idx"]))
    write_jsonl(path, rows)


def rows_for(run: str, benchmark: str, lang: str, items: list[dict], samples: list, en_ids: set[str]) -> list[dict]:
    rows = []
    for item, item_samples in zip(items, samples):
        for k, s in enumerate(item_samples):
            gold = item["answer"]
            rows.append(
                {
                    # --- trace_criteria input schema ---
                    "trace_id": f"{run}:{benchmark}:{lang}:{item['id']}#{k}",
                    "prompt_id": item["id"],
                    "source": run,
                    "domain": DOMAINS.get(benchmark, "other"),
                    "language": lang,
                    "prompt": item["messages"][-1]["content"],
                    "completion": s.completion,
                    "gold": gold if gold is None or isinstance(gold, str) else json.dumps(gold, ensure_ascii=False),
                    "finish_reason": s.finish_reason,
                    "sample_idx": k,
                    "en_trace_id": f"{run}:{benchmark}:en:{item['id']}#{k}" if lang == "it" and item["id"] in en_ids else None,
                    # --- ThinkBenchITA ---
                    "benchmark": benchmark,
                    "messages": item["messages"],
                    "thinking": s.thinking,
                    "answer": s.answer,
                    "think_closed": s.think_closed,
                    "tokens": {"prompt": s.prompt_tokens, "completion": s.completion_tokens, "thinking": s.thinking_tokens, "answer": s.answer_tokens},
                    "scorer": item["scorer"],
                    "meta": {k: v for k, v in item["meta"].items() if k not in ("test", "source_prompt", "canonical_solution", "public_tests")},
                    "score": None,
                }
            )
    return rows


def score_rows(rows: list[dict], items: dict[str, dict], workers: int) -> None:
    def one(row):
        try:
            return score(items[row["prompt_id"]], row["answer"])
        except Exception as e:  # noqa: BLE001 - one broken item must not lose a whole run
            logging.exception("scoring failed for %s", row["trace_id"])
            return {"correct": False, "scorer_error": repr(e)[:500]}

    sandboxed = rows and rows[0]["scorer"] == "code_exec"
    if sandboxed:
        rows.sort(key=lambda r: r["prompt_id"])  # keeps one item's tests cached across its samples
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(one, rows))
    else:
        results = [one(row) for row in rows]
    for row, result in zip(rows, results):
        row["score"] = result


def write_summary(run_dir: Path, all_metrics: dict, config: dict) -> None:
    (run_dir / "metrics.json").write_text(json.dumps(all_metrics, indent=2, ensure_ascii=False))
    ks = [k for k in config["ks"]]
    cols = [f"pass@{k}" for k in ks]
    lines = [f"# {run_dir.name}", "", f"Model: `{config['model']['path']}`", "", "| benchmark | lang | items | n | " + " | ".join(cols) + " | truncated | format ok | loops | trace ok | thinking (median tokens) | thinking mostly English | notes |", "|---|---|---|---|" + "---|" * (len(cols) + 7)]
    for benchmark, langs in all_metrics.items():
        for lang, m in langs.items():
            o = m["overall"]
            cells = [f"{o[c] * 100:.1f}" if c in o else "–" for c in cols]
            notes = []
            if o.get("n_scored_items", 0) < o["n_items"]:
                notes.append("awaiting judge" if benchmark == "xalpaca" else f"{o['n_items'] - o['n_scored_items']} unscored")
            if "parallel" in m:
                notes.append(f"shared ids ({m['parallel']['n_items']}): pass@1 {m['parallel'].get('pass@1', 0) * 100:.1f}")
            for key in ("loose_accuracy", "instruction_accuracy", "cell_accuracy", "off_list_rate"):
                if key in o:
                    notes.append(f"{key.replace('_', ' ')} {o[key] * 100:.1f}")
            if o.get("loop_rate") and config["benchmarks"].get(benchmark, {}).get("loop_note"):
                notes.append(config["benchmarks"][benchmark]["loop_note"])
            if "truncated_looping_rate" in o:
                notes.append(f"truncated outputs looping {o['truncated_looping_rate'] * 100:.0f}%")
            if "answer_mostly_en_rate" in o:
                notes.append(f"answer mostly English {o['answer_mostly_en_rate'] * 100:.0f}% (of the {o['answer_judged_rate'] * 100:.0f}% long enough to judge)")
            if "lang_ok_rate" in o:
                notes.append(f"thinking Italian in every paragraph {o['lang_ok_rate'] * 100:.0f}%, switches language {o['think_lang_switch_rate'] * 100:.0f}%")
            if m.get("length_vs_en"):
                r = m["length_vs_en"]
                notes.append(f"thinking vs English: x{r.get('median_think_tokens_ratio_it_vs_en', 0):.2f} tokens, x{r.get('median_think_words_ratio_it_vs_en', 0):.2f} words, {r.get('think_words_outlier_rate_it_vs_en', 0) * 100:.0f}% of items over x2 or under x0.5")
            trace = [
                f"{o['format_ok_rate'] * 100:.1f}%" if "format_ok_rate" in o else "–",
                f"{o['loop_rate'] * 100:.1f}%" if "loop_rate" in o else "–",
                f"{o['trace_ok_rate'] * 100:.1f}%" if "trace_ok_rate" in o else "–",
                f"{o['median_think_tokens']:.0f}" if "median_think_tokens" in o else "–",
                f"{o['think_mostly_en_rate'] * 100:.1f}%" if "think_mostly_en_rate" in o else "–",
            ]
            lines.append(f"| {benchmark} | {lang} | {o['n_items']} | {o['samples_per_item']} | " + " | ".join(cells) + f" | {o.get('truncated_rate', 0) * 100:.1f}% | " + " | ".join(trace) + f" | {'; '.join(notes)} |")
    lines += ["", "pass@1 is the mean over items of the fraction of correct samples; pass@k (k>1) is the unbiased estimator over the n samples. Only the final answer is scored; an output truncated inside the thinking block has an empty answer and counts as wrong. Format ok: one thinking block, opened and closed once, non-empty, followed by a non-empty answer, not truncated, no lost bytes. Loops: outputs that repeat themselves (repeated 4-grams, a repeated paragraph, or an ending stuck on one short sequence); \"truncated outputs looping\" separates loops from reasoning cut off by the token cap. Trace ok: format ok, no loop, and (Italian) no mostly-English paragraph in the thinking. Thinking mostly English: Italian outputs whose thinking has at least half English words; \"switches language\": thinking that moves between English and Italian paragraphs (src/trace_stats.py). Breakdowns are in metrics.json."]
    (run_dir / "summary.md").write_text("\n".join(lines) + "\n")


def shard_items(benchmark: str, lang: str, items: list[dict], shard: int, n_shards: int) -> list[dict]:
    """Every n-th item, from an offset fixed per file: each process gets a fair share of every
    benchmark, long and short ones alike, without estimating token counts."""
    offset = zlib.crc32(f"{benchmark}/{lang}".encode())
    return [item for k, item in enumerate(items) if (k + offset) % n_shards == shard]


def child_argv(argv: list[str]) -> list[str]:
    """The command line without --gpus and --stage (and their values)."""
    out, skip = [], False
    for token in argv:
        if token.startswith("--"):
            dropped = token.split("=")[0] in ("--gpus", "--stage")
            skip = dropped and "=" not in token  # the values follow as separate tokens
            if dropped:
                continue
        elif skip:
            continue
        out.append(token)
    return out


def generate_data_parallel(args, run_dir: Path, todo: list[tuple], tp: int, plan: list[tuple]) -> None:
    """One process per group of `tp` GPUs, each generating its share of what is left of every file
    into runs/{run}/_shards/{i}/ (saved as it goes); then the shards are merged, in item order,
    into the run folder with what was already there."""
    groups = [args.gpus[i : i + tp] for i in range(0, len(args.gpus) - tp + 1, tp)]
    procs = []
    for i, gpus in enumerate(groups):
        shard_dir = run_dir / "_shards" / str(i)
        shard_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, __file__, *child_argv(sys.argv[1:]), "--stage", "generate", "--shard", f"{i}/{len(groups)}"]
        with open(shard_dir / "run.log", "a") as log:
            procs.append(subprocess.Popen(cmd, env={**os.environ, "CUDA_VISIBLE_DEVICES": ",".join(gpus)}, stdout=log, stderr=subprocess.STDOUT))
        print(f"shard {i}/{len(groups)}: GPU {','.join(gpus)}, log {shard_dir / 'run.log'}", flush=True)
    codes = [p.wait() for p in procs]
    if any(codes):
        sys.exit(f"shard processes failed (exit codes {codes}); their finished outputs are in {run_dir}/_shards/: rerun the same command to resume")
    full = {(b, lang): items for b, lang, _, items, _ in plan}
    for benchmark, lang, *_ in todo:
        main_file = run_dir / benchmark / f"{lang}.jsonl"
        parts = [run_dir / "_shards" / str(i) / benchmark / f"{lang}.jsonl" for i in range(len(groups))]
        rows = (read_jsonl(main_file) if main_file.exists() else []) + [row for part in parts if part.exists() for row in read_jsonl(part)]
        order = {item["id"]: k for k, item in enumerate(full[benchmark, lang])}
        if {r["prompt_id"] for r in rows} != set(order):
            sys.exit(f"{benchmark}/{lang}: the outputs do not hold exactly the selected items (stale shards from another run? use --overwrite)")
        rows.sort(key=lambda r: (order[r["prompt_id"]], r["sample_idx"]))
        write_jsonl(main_file, rows)
        for part in parts:
            part.unlink(missing_ok=True)
    shard_config = yaml.safe_load(next((run_dir / "_shards").glob("*/config.yaml")).read_text())
    shard_config["command_line"] = {**vars(args), "data_parallel_groups": groups}
    (run_dir / "config.yaml").write_text(yaml.safe_dump(shard_config, sort_keys=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run name: outputs go to runs/{run}/")
    ap.add_argument("--config", default=str(ROOT / "config" / "eval.yaml"))
    ap.add_argument("--stage", choices=["all", "generate", "score"], default="all")
    ap.add_argument("--benchmarks", nargs="*")
    ap.add_argument("--langs", nargs="*", choices=["it", "en"])
    ap.add_argument("--model-config", help="config/models/{name}.yaml: model, think_delims and (rarely) sampling of the model under test")
    ap.add_argument("--model", help="override model.path")
    ap.add_argument("--gpus", nargs="+", help="GPU ids to use; more than tensor_parallel_size runs one process per group, each on a share of every file")
    ap.add_argument("--shard", help=argparse.SUPPRESS)  # "i/N": set by --gpus for its child processes
    ap.add_argument("--n", type=int, help="override samples per item for every benchmark")
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--max-model-len", type=int)
    ap.add_argument("--gpu-memory-utilization", type=float, help="fraction of the GPU vLLM may take (lower it on a shared GPU)")
    ap.add_argument("--kv-cache-dtype", help="override model.kv_cache_dtype, e.g. fp8: about twice the sequences at once, slightly different outputs")
    ap.add_argument("--limit", type=int, help="first N items of each file (smoke tests)")
    ap.add_argument("--overwrite", action="store_true", help="regenerate files that already exist")
    ap.add_argument("--no-thinking", action="store_true", help="save only the final answer: the trace checks are computed at generation time, the thinking text is not saved")
    args = ap.parse_args()

    config = yaml.safe_load(open(args.config))
    if args.model_config:
        model_config = yaml.safe_load(open(args.model_config))
        unknown = set(model_config) - {"model", "think_delims", "sampling"}
        if unknown:
            sys.exit(f"{args.model_config}: unknown keys {sorted(unknown)}")
        config["model"].update(model_config.get("model") or {})
        config["sampling"].update(model_config.get("sampling") or {})
        config["think_delims"] = model_config.get("think_delims", config["think_delims"])
    if args.model:
        config["model"]["path"] = args.model
    if args.max_model_len:
        config["model"]["max_model_len"] = args.max_model_len
    if args.gpu_memory_utilization:
        config["model"]["gpu_memory_utilization"] = args.gpu_memory_utilization
    if args.kv_cache_dtype:
        config["model"]["kv_cache_dtype"] = args.kv_cache_dtype
    if args.max_tokens:
        config["sampling"]["max_tokens"] = args.max_tokens
    run_dir = ROOT / "runs" / args.run
    run_dir.mkdir(parents=True, exist_ok=True)
    scoring = config.get("scoring", {})
    code_exec.LIMITS.update(
        timeout=scoring.get("code_timeout", 60),
        memory_mb=scoring.get("memory_mb", 4096),
        lcb_timeout_per_test=scoring.get("lcb_timeout_per_test", 6),
        lcb_timeout_total=scoring.get("lcb_timeout_total", 300),
    )

    plan = []
    for benchmark, spec in config["benchmarks"].items():
        spec = spec or {}
        if args.benchmarks and benchmark not in args.benchmarks:
            continue
        if not args.benchmarks and not spec.get("enabled", True):
            continue
        langs = [lang for lang in spec.get("langs", ["it", "en"]) if not args.langs or lang in args.langs]
        selected = {lang: select(benchmark, lang, spec, args.limit) for lang in langs}
        for lang in langs:
            if selected[lang]:
                plan.append((benchmark, lang, spec, selected[lang], {i["id"] for i in selected.get("en", [])}))
            else:
                print(f"skip {benchmark}/{lang}: no runnable items (not built, gated, or pending translation)")

    reader = None
    if args.stage in ("all", "generate"):
        n_for = {}  # samples per item, per benchmark
        for benchmark, _, spec, _, _ in plan:
            n_for[benchmark] = args.n or {"n": config["sampling"].get("n", 1), **(spec.get("sampling") or {})}["n"]
        if args.overwrite and not args.shard:
            for benchmark, lang, *_ in plan:
                (run_dir / benchmark / f"{lang}.jsonl").unlink(missing_ok=True)
        # what is left: items without all their samples in the run folder (resumes a stopped run)
        todo = []
        for benchmark, lang, spec, items, en_ids in plan:
            done = done_ids(run_dir / benchmark / f"{lang}.jsonl", n_for[benchmark])
            left = [i for i in items if i["id"] not in done]
            if left:
                todo.append((benchmark, lang, spec, left, en_ids))
        tp = config["model"].get("tensor_parallel_size", 1)
        if args.gpus and len(args.gpus) < tp:
            sys.exit(f"--gpus gives {len(args.gpus)} GPU(s), tensor_parallel_size is {tp}")
        if todo and args.gpus and len(args.gpus) >= 2 * tp and not args.shard:
            generate_data_parallel(args, run_dir, todo, tp, plan)
            todo = []
        out_dir = run_dir
        if todo and args.shard:
            shard, n_shards = map(int, args.shard.split("/"))
            out_dir = run_dir / "_shards" / str(shard)
            if args.overwrite:
                for b, lang, *_ in todo:
                    (out_dir / b / f"{lang}.jsonl").unlink(missing_ok=True)
            todo = [(b, lang, spec, shard_items(b, lang, items, shard, n_shards), en_ids) for b, lang, spec, items, en_ids in todo]
            todo = [(b, lang, spec, [i for i in items if i["id"] not in done_ids(out_dir / b / f"{lang}.jsonl", n_for[b])], en_ids)
                    for b, lang, spec, items, en_ids in todo]
            todo = [t for t in todo if t[3]]
        elif args.gpus:
            os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(args.gpus)  # before vLLM starts
        if todo:
            from src.generate import EvalReader

            model = config["model"]
            base = {k: v for k, v in config["sampling"].items() if k != "n"}
            reader = EvalReader(
                model["path"],
                think_delims=config["think_delims"],
                chat_template_kwargs=model.get("chat_template_kwargs"),
                max_model_len=model["max_model_len"],
                tensor_parallel_size=model.get("tensor_parallel_size", 1),
                gpu_memory_utilization=model.get("gpu_memory_utilization", 0.9),
                kv_cache_dtype=model.get("kv_cache_dtype", "auto"),
                **base,
            )
            (out_dir / "config.yaml").write_text(yaml.safe_dump({**config, "think_open_in_prompt": reader.think_open_in_prompt, "command_line": vars(args)}, sort_keys=False))
            batches = {}  # files with the same sampling settings are generated together
            for benchmark, lang, spec, items, en_ids in todo:
                sampling = {"n": config["sampling"].get("n", 1), **(spec.get("sampling") or {})}
                if args.n:
                    sampling["n"] = args.n
                batches.setdefault(json.dumps(sampling, sort_keys=True), []).append((benchmark, lang, items, en_ids))
            for key, jobs in batches.items():
                sampling = json.loads(key)
                print("generate " + ", ".join(f"{b}/{lang} ({len(items)})" for b, lang, items, _ in jobs) + f" x {sampling['n']}", flush=True)
                generate(reader, args.run, jobs, sampling, out_dir, config["think_delims"] if args.no_thinking else None)
        # item order in every file of the run, including files a stopped run completed before
        # it could sort them (rows are appended in completion order)
        for benchmark, lang, _, items, _ in plan:
            if (out_dir / benchmark / f"{lang}.jsonl").exists():
                sort_file(out_dir / benchmark / f"{lang}.jsonl", items)

    if args.stage in ("all", "score"):
        metrics_path = run_dir / "metrics.json"
        all_metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
        for benchmark, lang, spec, items, _ in plan:
            path = run_dir / benchmark / f"{lang}.jsonl"
            if not path.exists():
                continue
            rows = read_jsonl(path)
            print(f"score {benchmark}/{lang}: {len(rows)} outputs")
            judged = {r["trace_id"]: r["score"] for r in rows if r["scorer"] == "judge_pairwise" and r["score"] and r["score"].get("correct") is not None}
            score_rows(rows, {i["id"]: i for i in items}, scoring.get("workers", 8))
            for row in rows:  # keep judgments already made by xalpaca_judge.py
                if row["trace_id"] in judged:
                    row["score"] = judged[row["trace_id"]]
                if row["thinking"] is not None:  # --no-thinking rows keep the checks made at generation time
                    row["trace"] = trace_stats(row, config["think_delims"])
            write_jsonl(path, rows)
            entry = {"overall": metrics.summarise(rows, config["ks"])}
            for key in spec.get("group_by") or []:
                entry[f"by_{key}"] = metrics.grouped(rows, key, config["ks"])
            all_metrics.setdefault(benchmark, {})[lang] = entry
        # where the two languages do not cover the same ids, also report on the shared ones
        for benchmark, langs in all_metrics.items():
            files = {lang: run_dir / benchmark / f"{lang}.jsonl" for lang in ("it", "en")}
            if not all(f.exists() for f in files.values()):
                continue
            rows = {lang: read_jsonl(f) for lang, f in files.items()}
            ids = {lang: {r["prompt_id"] for r in rs} for lang, rs in rows.items()}
            for lang in ("it", "en"):
                if lang in langs:
                    langs[lang].pop("length_vs_en", None)
            if "it" in langs:
                langs["it"]["length_vs_en"] = metrics.length_ratio_vs_en(rows["it"], rows["en"])
            if ids["it"] != ids["en"] and ids["it"] & ids["en"]:
                shared = ids["it"] & ids["en"]
                for lang in ("it", "en"):
                    if lang in langs:
                        langs[lang]["parallel"] = metrics.summarise([r for r in rows[lang] if r["prompt_id"] in shared], config["ks"])
        write_summary(run_dir, all_metrics, config)
        write_run_report(run_dir, all_metrics, config["model"]["path"])
        print((run_dir / "summary.md").read_text())


if __name__ == "__main__":
    main()
