"""pass@k and the per-benchmark summary."""

from collections import Counter, defaultdict
from math import comb
from statistics import median


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased estimate of P(at least one of k samples is correct), from c correct out of n (Chen et al., 2021)."""
    if k > n:
        raise ValueError(f"pass@{k} needs at least {k} samples per item, got {n}")
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def summarise(rows: list[dict], ks: list[int]) -> dict:
    """Metrics for the scored output rows of one benchmark x language (one row per item x sample)."""
    by_item = defaultdict(list)
    for row in rows:
        by_item[row["prompt_id"]].append(row)
    scored = {i: s for i, s in by_item.items() if all(r["score"].get("correct") is not None for r in s)}
    n_samples = min((len(s) for s in by_item.values()), default=0)
    out = {"n_items": len(by_item), "n_scored_items": len(scored), "samples_per_item": n_samples}
    if scored:
        for k in ks:
            if k <= n_samples:
                values = [pass_at_k(len(s), sum(bool(r["score"]["correct"]) for r in s), k) for s in scored.values()]
                out[f"pass@{k}"] = sum(values) / len(values)
    flat = [r for s in by_item.values() for r in s]
    if flat:
        out["truncated_rate"] = sum(r["finish_reason"] == "length" for r in flat) / len(flat)
        out["think_closed_rate"] = sum(bool(r["think_closed"]) for r in flat) / len(flat)
        out["empty_answer_rate"] = sum(not r["answer"].strip() for r in flat) / len(flat)
        out["mean_thinking_tokens"] = sum(r["tokens"]["thinking"] for r in flat) / len(flat)
        # scorer-specific extras, averaged over samples
        for key, name in (("correct_loose", "loose_accuracy"), ("cell_accuracy", "cell_accuracy"), ("off_list", "off_list_rate")):
            values = [r["score"][key] for r in flat if key in r["score"]]
            if values:
                out[name] = sum(values) / len(values)
        follow = [f for r in flat for f in r["score"].get("follow_strict", [])]
        if follow:
            out["instruction_accuracy"] = sum(follow) / len(follow)
        out.update(trace_summary(flat))
    return out


def trace_summary(rows: list[dict]) -> dict:
    """Format, length and language of the traces (src/trace_stats.py), over samples."""
    traces = [r for r in rows if r.get("trace")]
    if not traces:
        return {}
    t = [r["trace"] for r in traces]
    out = {
        "format_ok_rate": sum(x["format_ok"] for x in t) / len(t),
        "format_problems": dict(Counter(x["format_status"] for x in t if x["format_status"])),
        "median_think_tokens": median(x["think_tokens"] for x in t),
        "median_think_words": median(x["think_words"] for x in t),
    }
    if all("loop" in x for x in t):  # outputs scored before the loop check have no loop field
        truncated = [x for x in t if x["format_status"] == "truncated"]
        out["loop_rate"] = sum(x["loop"] for x in t) / len(t)
        out["loop_triggers"] = dict(Counter(trig for x in t if x["loop_status"] for trig in x["loop_status"].split("+")))
        if truncated:
            out["truncated_looping_rate"] = sum(x["loop"] for x in truncated) / len(truncated)
    for label, ok in (("correct", True), ("wrong", False)):
        lengths = [r["trace"]["think_tokens"] for r in traces if r["score"].get("correct") is ok]
        if lengths:
            out[f"median_think_tokens_{label}"] = median(lengths)
    out["trace_ok_rate"] = sum(x.get("trace_ok", False) for x in t) / len(t)
    if any("lang_ok" in x for x in t):
        out["lang_ok_rate"] = sum(x.get("lang_ok", False) for x in t) / len(t)
        out["think_lang_switch_rate"] = sum(x.get("think_lang_switches", 0) > 0 for x in t) / len(t)
    judged = [x["answer_mostly_en"] for x in t if x.get("answer_mostly_en") is not None]
    if judged:
        out["answer_judged_rate"] = len(judged) / len(t)
        out["answer_mostly_en_rate"] = sum(judged) / len(judged)  # over answers long enough to judge
    rates = [x["think_en_word_rate"] for x in t if x.get("think_en_word_rate") is not None]
    if rates:
        out["median_think_en_word_rate"] = median(rates)
        out["think_mostly_en_rate"] = sum(r >= 0.5 for r in rates) / len(t)
        out["think_any_en_paragraph_rate"] = sum(x.get("think_en_paragraphs", 0) > 0 for x in t) / len(t)
    return out


LENGTH_OUTLIER = 2.0


def length_ratio_vs_en(it_rows: list[dict], en_rows: list[dict]) -> dict:
    """Median over shared items of (mean Italian thinking length / mean English), in tokens and words."""
    def per_item(rows, key):
        by = defaultdict(list)
        for r in rows:
            if r.get("trace"):
                by[r["prompt_id"]].append(r["trace"][key])
        return {i: sum(v) / len(v) for i, v in by.items()}

    out = {}
    for key in ("think_tokens", "think_words"):
        it, en = per_item(it_rows, key), per_item(en_rows, key)
        ratios = [it[i] / en[i] for i in it.keys() & en.keys() if en[i] > 0]
        if ratios:
            out[f"median_{key}_ratio_it_vs_en"] = median(ratios)
            # items whose Italian thinking is more than twice, or less than half, the English length
            out[f"{key}_outlier_rate_it_vs_en"] = sum(r > LENGTH_OUTLIER or r < 1 / LENGTH_OUTLIER for r in ratios) / len(ratios)
    return out


def grouped(rows: list[dict], key: str, ks: list[int]) -> dict:
    groups = defaultdict(list)
    for row in rows:
        groups[str(row["meta"].get(key))].append(row)
    return {value: summarise(group, ks) for value, group in sorted(groups.items())}
