"""Inspection report and side-by-side sample for one built benchmark."""

import csv
import random
from collections import Counter
from pathlib import Path

from .schema import Built, Item, write_jsonl

SAMPLE_SEED = 20261006
SAMPLE_SIZE = 20


def validate(built: Built) -> list[dict]:
    """Format checks on the converted items (source problems are logged by the loaders)."""
    problems = []

    def add(item: Item, kind: str, detail: str = ""):
        problems.append({"id": item.id, "lang": item.lang, "kind": kind, "detail": detail})

    for lang, items in built.items.items():
        for id_, n in Counter(i.id for i in items).items():
            if n > 1:
                problems.append({"id": id_, "lang": lang, "kind": "duplicate_id", "detail": f"{n} rows"})
        for item in items:
            if item.pending:
                continue
            if not item.messages or any(not (m.get("content") or "").strip() for m in item.messages):
                add(item, "empty_prompt")
            if item.scorer in ("math_verify", "mcq", "exact_match", "grid_match") and item.answer in (None, "", {}, []):
                add(item, "empty_gold")
            if item.scorer == "math_verify":
                from .scorers.answers import parse_math

                try:
                    parsed = parse_math(str(item.answer))
                except Exception as e:  # noqa: BLE001
                    parsed, detail = [], repr(e)
                else:
                    detail = ""
                if not parsed:
                    add(item, "gold_not_parsed_by_math_verify", f"{item.answer!r} {detail}".strip())
            if item.scorer == "mcq" and item.answer not in item.meta.get("choices", []):
                add(item, "gold_not_a_choice", f"{item.answer!r} not in {item.meta.get('choices')}")
            if item.scorer == "ifeval":
                from .scorers.ifeval import _checkers

                unknown = [i for i in item.meta["instruction_id_list"] if i not in _checkers().INSTRUCTION_DICT]
                if unknown:
                    add(item, "unknown_instruction", ", ".join(unknown))
    problems += _reference_solutions(built)
    return problems


def _reference_solutions(built: Built) -> list[dict]:
    """Run every reference solution against its own tests: a failure means the
    TEST is broken, and no model answer can pass that item."""
    from concurrent.futures import ThreadPoolExecutor
    from dataclasses import asdict

    from .scorers import sandbox
    from .scorers.code_exec import score_code_exec

    items = [i for i in built.items.get("en", []) if i.scorer == "code_exec" and i.meta.get("canonical_solution") and not i.pending]
    if not items or not sandbox.available():
        return []

    def run(item: Item):
        code = item.meta["canonical_solution"]
        if item.meta["test_format"] == "humaneval":
            code = item.meta["source_prompt"] + code
        return score_code_exec(asdict(item), f"```python\n{code}\n```")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, items))
    return [
        {"id": i.id, "lang": None, "kind": "reference_solution_fails_its_test", "detail": f"{r['status']}: {r['stderr'].strip().splitlines()[-1] if r['stderr'].strip() else ''}"}
        for i, r in zip(items, results)
        if not r["correct"]
    ]


def alignment(built: Built) -> dict:
    it = {i.id for i in built.items.get("it", [])}
    en = {i.id for i in built.items.get("en", [])}
    return {"both": len(it & en), "it_only": sorted(it - en), "en_only": sorted(en - it)}


def _text(item: Item | None) -> str:
    if item is None:
        return ""
    if item.pending:
        return "(pending translation)"
    return item.messages[-1]["content"]


def _gold(item: Item | None) -> str:
    return "" if item is None or item.answer is None else str(item.answer)


def sample_pairs(built: Built) -> list[dict]:
    it = {i.id: i for i in built.items.get("it", [])}
    en = {i.id: i for i in built.items.get("en", [])}
    ids = sorted(set(it) & set(en)) or sorted(set(it) | set(en))
    # on-by-default items only, when the benchmark has a default subset
    default = [i for i in ids if (it.get(i) or en.get(i)).meta.get("default", True)]
    chosen = sorted(random.Random(SAMPLE_SEED).sample(default, min(SAMPLE_SIZE, len(default))))
    return [
        {"id": i, "it": _text(it.get(i)), "en": _text(en.get(i)), "gold_it": _gold(it.get(i)), "gold_en": _gold(en.get(i))}
        for i in chosen
    ]


def write_sample(name: str, built: Built, out_dir: Path) -> int:
    rows = sample_pairs(built)
    if not rows:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[*rows[0], "translation_ok", "notes"])
        writer.writeheader()
        writer.writerows(rows)
    lines = [f"# {built.info['name']}: {len(rows)} sampled items, Italian / English side by side", ""]
    lines.append(f"Random sample (seed {SAMPLE_SEED}) of the prompts exactly as the model receives them. The CSV next to this file has the same rows plus two empty columns for the manual check.")
    for row in rows:
        fence = "`````"
        lines += ["", f"## {row['id']}", "", "**IT**", "", fence, row["it"], fence, "", "**EN**", "", fence, row["en"], fence, ""]
        if row["gold_it"] or row["gold_en"]:
            lines += [f"Gold: it `{row['gold_it']}` · en `{row['gold_en']}`", ""]
    (out_dir / f"{name}.md").write_text("\n".join(lines), encoding="utf-8")
    return len(rows)


def write_report(name: str, built: Built, report_dir: Path, private_dir: Path | None) -> dict:
    """Write reports/{name}.md and the issue log; return the summary row.

    `private_dir` is set for gated sources: their issue details can quote
    benchmark content, so the log goes next to the data (git-ignored) and the
    report only shows counts.
    """
    info, items = built.info, built.items
    problems = validate(built)
    issues = built.issues.rows + problems
    align = alignment(built)
    counts = {lang: len(rows) for lang, rows in items.items()}
    pending = {lang: sum(i.pending for i in rows) for lang, rows in items.items()}
    scorers = Counter(i.scorer for rows in items.values() for i in rows)

    log_dir = private_dir or report_dir / "issues"
    log_path = log_dir / ("issues.jsonl" if private_dir else f"{name}.jsonl")
    write_jsonl(log_path, issues)

    md = [f"# {info['name']} (`{name}`)", ""]
    md += [f"- **Source:** {info['source']}", f"- **Paper:** {info['paper']}", f"- **Licence:** {info['licence']}", f"- **Scorer:** {info['scorer']}", ""]
    md += ["## Items", "", "| lang | items | ready | pending translation |", "|---|---|---|---|"]
    for lang in ("it", "en"):
        if lang in counts:
            md.append(f"| {lang} | {counts[lang]} | {counts[lang] - pending[lang]} | {pending[lang]} |")
        else:
            md.append(f"| {lang} | – (no {('Italian' if lang == 'it' else 'English')} side) | | |")
    md += ["", "Scorer per item: " + ", ".join(f"`{s}` {n}" for s, n in scorers.most_common()) + "." if scorers else "No items were built (see below).", ""]
    default = [i for rows in items.values() for i in rows if "default" in i.meta]
    if default:
        on = Counter((i.lang, i.meta.get("level")) for i in default if i.meta["default"])
        md += ["On by default: " + ", ".join(f"{lang}/{level} {n}" for (lang, level), n in sorted(on.items())) + ".", ""]

    md += ["## ID alignment between Italian and English", ""]
    if "it" in items and "en" in items:
        md.append(f"- ids in both languages: **{align['both']}**")
        for key, label in (("it_only", "only in Italian"), ("en_only", "only in English")):
            ids = align[key]
            shown = ", ".join(f"`{i}`" for i in ids[:10]) + (" …" if len(ids) > 10 else "")
            md.append(f"- {label}: **{len(ids)}**" + (f" ({shown})" if ids else ""))
    else:
        md.append("- single-language benchmark: nothing to align.")
    md.append("")

    md += ["## Missing or malformed items", ""]
    if issues:
        by_kind = Counter(r["kind"] for r in issues)
        md += ["| kind | count | examples |", "|---|---|---|"]
        for kind, n in by_kind.most_common():
            rows = [r for r in issues if r["kind"] == kind]
            if private_dir:
                example = "(details in the local issue log)"
            else:
                example = "; ".join(f"`{r['id'] or '-'}`" + (f" {r['detail']}" if r["detail"] else "") for r in rows[:3]).replace("|", "\\|").replace("\n", " ")
            md.append(f"| {kind} | {n} | {example[:400]} |")
        where = f"`data/{name}/issues.jsonl` (local only)" if private_dir else f"[issues/{name}.jsonl](issues/{name}.jsonl)"
        md += ["", f"Full log: {where}. Nothing listed here was edited in the data."]
    else:
        md.append("None found.")
    md += ["", "## Notes and decisions", ""] + [f"- {note}" for note in info["notes"]] + [""]
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{name}.md").write_text("\n".join(md), encoding="utf-8")
    return {"name": name, "title": info["name"], "counts": counts, "pending": pending, "both": align["both"], "issues": len(issues), "scorer": info["scorer"]}
