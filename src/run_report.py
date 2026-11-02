"""runs/{run}/report.md: Italian vs English per benchmark, the thinking checks, and outputs to read.

Written by run_eval.py after scoring, next to summary.md (which keeps one row per file). The
report may quote prompts and outputs of gated benchmarks (GPQA): runs/ is git-ignored, keep it so.
"""

import json
from pathlib import Path

from .schema import read_jsonl

N_WRONG, N_TRUNCATED, TAIL = 3, 2, 400


def pct(x) -> str:
    return "–" if x is None else f"{x * 100:.1f}"


def num(x) -> str:
    return "–" if x is None else f"{x:.0f}"


def tail(text: str, n: int = TAIL) -> str:
    text = (text or "").strip()
    return ("…" + text[-n:]) if len(text) > n else text


def examples(rows: list[dict]) -> list[str]:
    """A few wrong answers (not truncated) and truncated outputs, the first ones in file order."""
    wrong = [r for r in rows if r["score"] and r["score"].get("correct") is False and r["finish_reason"] != "length"][:N_WRONG]
    truncated = [r for r in rows if r["finish_reason"] == "length"][:N_TRUNCATED]
    out = []
    for label, picked in (("wrong", wrong), ("truncated", truncated)):
        for r in picked:
            t = r.get("trace") or {}
            flags = ", ".join(f for f, on in (("loop: " + str(t.get("loop_status")), t.get("loop")), ("English paragraphs", t.get("lang_ok") is False)) if on)
            out += [
                f"<details><summary>{label}: <code>{r['trace_id']}</code> ({t.get('think_tokens', '?')} thinking tokens{', ' + flags if flags else ''})</summary>",
                "",
                f"**Gold:** `{tail(str(r['gold']), 200)}`",
                "",
                "**End of thinking:**",
                "```text",
                tail(r["thinking"]).replace("```", "'''") if r["thinking"] is not None else "(not saved: run with --no-thinking)",
                "```",
                "**Answer:**",
                "```text",
                tail(r["answer"]).replace("```", "'''") or "(empty)",
                "```",
                "</details>",
                "",
            ]
    return out


def write_run_report(run_dir: Path, all_metrics: dict, model: str) -> None:
    lines = [f"# {run_dir.name}: report", "", f"Model: `{model}`. One row per benchmark; details and outputs to read below. Rates in %.", ""]
    lines += [
        "| benchmark | pass@1 it | pass@1 en | it − en | trace ok it | trace ok en | Italian thinking mostly English | thinking it/en (words) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for benchmark, langs in all_metrics.items():
        o = {lang: m["overall"] for lang, m in langs.items()}
        # on the shared ids when the two languages cover different items
        p1 = {lang: (langs[lang].get("parallel") or o[lang]).get("pass@1") for lang in o}
        gap = f"{(p1['it'] - p1['en']) * 100:+.1f}" if p1.get("it") is not None and p1.get("en") is not None else "–"
        ratio = (langs.get("it", {}).get("length_vs_en") or {}).get("median_think_words_ratio_it_vs_en")
        lines.append(
            f"| {benchmark} | {pct(p1.get('it'))} | {pct(p1.get('en'))} | {gap} | {pct(o.get('it', {}).get('trace_ok_rate'))} | "
            f"{pct(o.get('en', {}).get('trace_ok_rate'))} | {pct(o.get('it', {}).get('think_mostly_en_rate'))} | {f'x{ratio:.2f}' if ratio else '–'} |"
        )
    lines += ["", "pass@1 it − en is on the items both languages have. Trace ok: format ok, no loop, and (Italian) no mostly-English paragraph.", ""]

    for benchmark, langs in all_metrics.items():
        lines += [f"## {benchmark}", "", "| | " + " | ".join(langs) + " |", "|---|" + "---|" * len(langs)]
        o = {lang: m["overall"] for lang, m in langs.items()}
        rows_spec = [
            ("items x samples", lambda x: f"{x['n_items']} x {x['samples_per_item']}"),
            ("pass@1", lambda x: pct(x.get("pass@1"))),
            ("truncated", lambda x: pct(x.get("truncated_rate"))),
            ("format problems", lambda x: ", ".join(f"{k} {v}" for k, v in x.get("format_problems", {}).items()) or "none"),
            ("loops", lambda x: pct(x.get("loop_rate"))),
            ("truncated outputs that loop", lambda x: pct(x.get("truncated_looping_rate"))),
            ("thinking, median tokens (correct / wrong)", lambda x: f"{num(x.get('median_think_tokens'))} ({num(x.get('median_think_tokens_correct'))} / {num(x.get('median_think_tokens_wrong'))})"),
            ("thinking Italian in every paragraph", lambda x: pct(x.get("lang_ok_rate"))),
            ("thinking switches language", lambda x: pct(x.get("think_lang_switch_rate"))),
            ("median share of English words in thinking", lambda x: pct(x.get("median_think_en_word_rate"))),
            ("answer mostly English (of answers long enough to judge)", lambda x: pct(x.get("answer_mostly_en_rate"))),
        ]
        for label, fn in rows_spec:
            lines.append(f"| {label} | " + " | ".join(fn(o[lang]) for lang in langs) + " |")
        it_len = langs.get("it", {}).get("length_vs_en")
        if it_len:
            lines += ["", f"Italian vs English thinking length on shared items: median x{it_len.get('median_think_words_ratio_it_vs_en', 0):.2f} words; "
                      f"{pct(it_len.get('think_words_outlier_rate_it_vs_en'))}% of items over x2 or under x0.5."]
        for lang in langs:
            path = run_dir / benchmark / f"{lang}.jsonl"
            if path.exists():
                lines += ["", f"### {benchmark}/{lang}: outputs to read", ""] + (examples(read_jsonl(path)) or ["None wrong or truncated.", ""])
    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":  # rebuild the report of an existing run: python -m src.run_report runs/{run}
    import sys

    import yaml

    run_dir = Path(sys.argv[1])
    model = yaml.safe_load((run_dir / "config.yaml").read_text())["model"]["path"]
    write_run_report(run_dir, json.loads((run_dir / "metrics.json").read_text()), model)
