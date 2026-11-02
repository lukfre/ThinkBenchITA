"""Italian side of the code benchmarks from our translation (HumanEval+, MBPP+, LiveCodeBench).

translation_export.py writes the English statements to data/_translation/export/ (masking below); the Cineca
pipeline (docs/translation_handoff.md) returns them in data/_translation/returned/. This
module checks each returned row again and builds the Italian item; a row that fails a check stays
a placeholder and is logged (kind `translation_check_failed`). The returned files are git-ignored
like the rest of data/; config/translation/manifest.json (tracked) pins their sha256, and a file
that does not match is refused.

LiveCodeBench: the ⟦OUT_n⟧ placeholders are filled with the Italian output words of
lcb_output_words_it.json; the scorer maps the expected test outputs through the same words
(meta.output_word_map). Hand repairs of the returned text are in REPAIRS, applied before the
checks and logged; the returned text is kept in meta.translation_returned.
"""

import ast
import hashlib
import json
import re
from pathlib import Path

from .. import prompts
from ..schema import DATA_DIR, ROOT, Issues, Item, user

RETURNED = DATA_DIR / "_translation" / "returned"
MANIFEST = ROOT / "config" / "translation" / "manifest.json"
OUTPUT_WORDS_IT = json.loads((Path(__file__).parent / "lcb_output_words_it.json").read_text(encoding="utf-8"))["words"]

# (id, returned text, our text): sentences the masking or the translation got wrong, fixed by hand
REPAIRS = {
    "livecodebench": [
        # a masked "No" opening an explanation ("No sequence X satisfies ...") is prose, not an output word
        ("lcb-abc307_b", "⟦OUT_2⟧ due stringhe distinte tra S_1, S_2 e S_3 formano un palindromo quando vengono concatenate.",
         "Nessuna coppia di stringhe distinte tra S_1, S_2 e S_3 forma un palindromo quando le due stringhe vengono concatenate."),
        ("lcb-abc327_d", "⟦OUT_2⟧ la sequenza X soddisfa la condizione", "Nessuna sequenza X soddisfa la condizione"),
        ("lcb-abc362_c", "⟦OUT_2⟧ sequenza X soddisfa le condizioni.", "Nessuna sequenza X soddisfa le condizioni."),
        # the accepted spellings of the (now Italian) positive answer
        ("lcb-1873_A", '"yEs", "yes", "Yes" e "⟦OUT_1⟧"', '"sÌ", "sì", "Sì" e "⟦OUT_1⟧"'),
        ("lcb-1883_B", '"yEs", "yes", "Yes" e "⟦OUT_1⟧"', '"sÌ", "sì", "Sì" e "⟦OUT_1⟧"'),
    ],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def returned_rows(benchmark: str) -> tuple[dict, dict] | None:
    """(rows by id, pipeline manifest), or None when the translation has not come back."""
    path = RETURNED / f"{benchmark}.jsonl"
    if not path.exists() or not MANIFEST.exists():
        return None
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if sha256(path) != manifest["benchmarks"][benchmark]["sha256"]:
        raise ValueError(f"{path} does not match config/translation/manifest.json: not the reviewed translation")
    lines = [line for line in path.read_text(encoding="utf-8").split("\n") if line]  # not splitlines(): U+2028 occurs in strings
    return {r["id"]: r for r in map(json.loads, lines)}, manifest


# --- masking of the LiveCodeBench output words (used by translation_export.py, recomputed here) ---

# (item id, word) -> text around an occurrence that is prose, not an output word
MASK_SKIP = {("lcb-abc310_b", "No"): ["No other pair"]}


def mask(item_id: str, text: str, words: list[str]) -> tuple[str, dict[str, str]]:
    placeholders = {}
    for word in sorted((w for w in words if len(w) > 1), key=len, reverse=True):
        tag = f"⟦OUT_{len(placeholders) + 1}⟧"
        skip = MASK_SKIP.get((item_id, word), [])
        keep = {m.start() + c.index(word) for c in skip for m in re.finditer(re.escape(c), text)}
        pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)")
        new = pattern.sub(lambda m: m.group(0) if m.start() in keep else tag, text)
        if new != text:
            placeholders[tag] = word
            text = new
    return text, placeholders


# --- checks: what must survive translation unchanged ---


def _strip_docstrings(tree: ast.AST) -> str:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def _lines(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if line.strip()}


def check_humaneval(en: str, it: str) -> list[str]:
    failed = []
    try:
        if _strip_docstrings(ast.parse(en)) != _strip_docstrings(ast.parse(it)):
            failed.append("code_changed")
    except SyntaxError:
        return ["not_python"]
    en_lines, it_lines = en.splitlines(), _lines(it)
    for k, line in enumerate(en_lines):
        if line.strip().startswith(">>>"):
            result = en_lines[k + 1].strip() if k + 1 < len(en_lines) else ""
            if line.strip() not in it_lines or (result and not result.startswith(">>>") and result not in it_lines):
                failed.append("doctest_changed")
                break
    return failed


def check_mbpp(en: str, it: str) -> list[str]:
    asserts = [line.strip() for line in en.splitlines() if line.strip().startswith("assert")]
    return [] if all(a in _lines(it) for a in asserts) else ["assert_changed"]


def check_lcb(en_masked: str, it: str, public_tests: list[dict]) -> list[str]:
    failed = []
    if any(en_masked.count(p) != it.count(p) for p in set(re.findall(r"⟦OUT_\d+⟧", en_masked + it))):
        failed.append("placeholders_changed")
    en_formulas = {m for line in en_masked.splitlines() for m in re.findall(r"\$[^$\n]+\$", line)}
    if not en_formulas <= {m for line in it.splitlines() for m in re.findall(r"\$[^$\n]+\$", line)}:
        failed.append("formula_changed")
    # stdin samples: every line of a sample that the English statement shows must be in the Italian one
    en_lines, it_lines = _lines(en_masked), _lines(it)
    for test in public_tests:
        if test.get("testtype") == "stdin":
            shown = [line for line in _lines(test["input"]) | _lines(test["output"]) if line in en_lines]
            if not all(line in it_lines for line in shown):
                failed.append("sample_changed")
                break
    return failed


# --- build ---


def fill(benchmark: str, en_items: list[Item], placeholders: list[Item], issues: Issues) -> list[Item]:
    got = returned_rows(benchmark)
    if got is None:
        return placeholders
    rows, manifest = got
    repairs = {}
    for item_id, old, new in REPAIRS.get(benchmark, []):
        repairs.setdefault(item_id, []).append((old, new))
    en_by_id = {e.id: e for e in en_items}
    out = []
    for ph in placeholders:
        row, en = rows.get(ph.id), en_by_id[ph.id]
        if row is None or row.get("status") != "ok":
            issues.add("translation_missing", f"no usable translation (status {row and row.get('status')})", ph.id, "it")
            out.append(ph)
            continue
        # the checks compare the returned text with what was exported, before our repairs
        text, src_en, word_map = row["text_it"], en.meta["source_prompt"], {}
        if benchmark == "humaneval":
            failed = check_humaneval(src_en, text)
        elif benchmark == "mbppplus":
            failed = check_mbpp(src_en, text)
        else:
            masked, placeholders_map = mask(ph.id, src_en, en.meta["fixed_output_words"])  # what was exported
            failed = check_lcb(masked, text, en.meta["public_tests"])
        if failed:
            issues.add("translation_check_failed", ", ".join(failed), ph.id, "it")
            out.append(ph)
            continue
        applied = []
        for old, new in repairs.get(ph.id, []):
            if text.count(old) != 1:
                raise ValueError(f"{ph.id}: repair text not found once: {old[:60]!r}")
            text = text.replace(old, new)
            applied.append({"returned": old, "ours": new})
        if applied:
            issues.add("repaired", f"translation edited by hand: {'; '.join(a['ours'][:80] for a in applied)}", ph.id, "it")
        if benchmark == "livecodebench":
            word_map = {w: OUTPUT_WORDS_IT[w] for w in placeholders_map.values()}
            for tag, word in placeholders_map.items():
                text = text.replace(tag, OUTPUT_WORDS_IT[word])
        # every English meta field, so the two languages share one schema (load_dataset needs it)
        meta = {k: v for k, v in en.meta.items() if k != "source_prompt"}
        meta.update(
            source_prompt=text,
            source_prompt_en=src_en,
            translation={"model": manifest["model"], "revision": manifest["revision"], "notes": row.get("notes", "")},
        )
        if applied:
            meta.update(repaired=applied, translation_returned=row["text_it"])
        if benchmark == "livecodebench":
            meta["output_word_map"] = {w: it for w, it in word_map.items() if w != it}
            messages = prompts.lcb_messages("it", text, en.meta["starter_code"])
        else:
            messages = user(prompts.evalplus_prompt("it", text))
        out.append(Item(id=ph.id, lang="it", messages=messages, answer=en.answer, scorer=en.scorer, meta=meta))
    return out
