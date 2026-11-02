"""Export the code benchmarks' English statements for translation (HumanEval+, MBPP+, LiveCodeBench).

    uv run python translation_export.py      # after prepare.py

Writes data/_translation/export/{benchmark}.jsonl, one row per item:
  id, benchmark, text (what to translate), rule (what to keep unchanged), placeholders.

LiveCodeBench: the words a program must print (meta.fixed_output_words, e.g. Yes/No) are replaced
in `text` by placeholders ⟦OUT_1⟧, ⟦OUT_2⟧..., listed in `placeholders` ({placeholder: word}), so the
translation cannot touch them; we put back translated words afterwards and map the test outputs to
them (README, translation queue). Not masked: single letters (lcb-abc336_a prints L, o, n, g, which
are everywhere in the text) and the occurrences in MASK_SKIP, where the word is prose, not output.

The translations come back as data/_translation/returned/{benchmark}.jsonl (docs/translation_handoff.md).
"""

import hashlib
import json

from src.loaders.translated import mask
from src.schema import DATA_DIR, read_jsonl

OUT = DATA_DIR / "_translation" / "export"
BENCHMARKS = ["humaneval", "mbppplus", "livecodebench"]
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for benchmark in BENCHMARKS:
        en = {i["id"]: i for i in read_jsonl(DATA_DIR / benchmark / "en.jsonl")}
        it = read_jsonl(DATA_DIR / benchmark / "it.jsonl")
        rows = []
        for placeholder in it:
            item = en[placeholder["id"]]
            text, tags = item["meta"]["source_prompt"], {}
            if benchmark == "livecodebench":
                text, tags = mask(item["id"], text, item["meta"]["fixed_output_words"])
            rows.append({"id": item["id"], "benchmark": benchmark, "text": text, "rule": placeholder["meta"]["translation_rule"], "placeholders": tags})
        path = OUT / f"{benchmark}.jsonl"
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        manifest[benchmark] = {
            "rows": len(rows),
            "masked_rows": sum(bool(r["placeholders"]) for r in rows),
            "chars": sum(len(r["text"]) for r in rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
