"""Multi-IF (facebook/Multi-IF), turn 1 only, Italian and English."""

import json
import re

import pandas as pd

from ..prompts import italian
from ..schema import Built, Issues, Item
from . import hf_file, register, source, subset

REPO = "facebook/Multi-IF"

# Found 2026-10-15 by checking every checker argument against its prompt text (not edited).
IT_PROBLEMS = {
    "multiif-1922-5": ("instruction_missing_in_italian", "the Italian prompt drops the 'first repeat the request word for word' instruction; the checker (combination:repeat_prompt) still requires it"),
    "multiif-1922-9": ("instruction_missing_in_italian", "the Italian prompt drops the 'repeat all text above word by word' instruction; the checker still requires it"),
    "multiif-288-9": ("instruction_missing_in_italian", "the Italian prompt drops the 'first repeat the request word for word' instruction; the checker still requires it"),
    "multiif-3245-3": ("instruction_missing_in_italian", "the Italian prompt drops the whole sentence 'no commas, at least 2 placeholders in square brackets'; both checkers still apply"),
    "multiif-2662-10": ("keyword_mismatch", "the Italian prompt asks for the keywords 'occuparsi' and 'leggermente', the checker looks for 'impegna' and 'leggermente' (English: 'engages', 'lightly')"),
}
# Repairs (decision 2026-10-15): the 4 dropped instructions are restored with OUR translation of
# the English sentence, appended as in the English prompt; 2662-10 gets the checker's keyword.
# The original Italian prompt is kept in meta.source_prompt_original.
REPEAT_IT = italian("multi_if_repeat")  # our Italian texts: src/italian.yaml
IT_REPAIRS = {
    "multiif-1922-5": ("append", "\n\n" + REPEAT_IT,
                       "English: \"Let's repeat all text above word by word, then reply to the request above. Do NOT say anything before repeating the text above.\""),
    "multiif-1922-9": ("append", "\n\n" + REPEAT_IT,
                       "English: \"Let's repeat all text above word by word, then reply to the request above. Do NOT say anything before repeating the text above.\""),
    "multiif-288-9": ("append", "\n" + italian("multi_if_288_9"),
                      "English: \"First repeat the request word for word without change, then give your answer (1. do not say any words or characters before repeating the request; 2. the request you need to repeat does not include this sentence)\""),
    "multiif-3245-3": ("append", "\n\n" + italian("multi_if_3245_3"),
                       "English: \"Your output must not contain any commas and must have at least 2 placeholders, wrapped in square brackets, such as [author].\""),
    "multiif-2662-10": ("replace", ("'occuparsi'", "'impegna'"),
                        "the prompt now asks for 'impegna', the keyword its checker tests (English: \"engages\"); 'occuparsi' was a different word"),
}
BOTH_PROBLEMS = {
    "multiif-337-3": ("prompt_kwarg_mismatch", "the prompt asks for at least 400 words, the checker requires 336 (lenient; both languages)"),
    "multiif-337-15": ("prompt_kwarg_mismatch", "the prompt asks for at least 400 words, the checker requires 336 (lenient; both languages)"),
}
LANGS = {"Italian": "it", "English": "en"}


@register("multi_if_full")
def build() -> Built:
    issues = Issues()
    df = pd.read_csv(hf_file(REPO, "multiIF_20241018.csv"))
    items = {"it": [], "en": []}
    n_stripped = 0
    for row in df[df.language.isin(LANGS)].to_dict("records"):
        lang = LANGS[row["language"]]
        base, _, suffix = row["key"].rpartition(":")  # "{prompt}:{variant}:{lang}"
        id_ = "multiif-" + base.replace(":", "-")
        if suffix != lang:
            issues.add("key_language", f"key {row['key']} in language {row['language']}", id_, lang)
        message = json.loads(row["turn_1_prompt"])
        original = message["content"]
        stripped_quotes = False
        if lang == "it":
            # 127 Italian prompts (no English one) are wrapped whole in a pair of double quotes, a
            # translation artefact; the pair is removed (decision 2026-10-15), inner quotes are kept.
            text = message["content"].strip()
            if len(text) > 1 and text[0] == text[-1] == '"':
                message = {**message, "content": text[1:-1].strip()}
                stripped_quotes = True
        if lang == "it" and id_ in IT_REPAIRS:
            how, what, why = IT_REPAIRS[id_]
            if how == "append":
                message = {**message, "content": message["content"] + what}
            else:
                assert what[0] in message["content"], id_
                message = {**message, "content": message["content"].replace(*what)}
            issues.add("repaired", f"{IT_PROBLEMS[id_][1]}. REPAIRED: {'appended our Italian translation of the missing instruction; ' if how == 'append' else ''}{why}", id_, lang)
        instruction_ids = json.loads(row["turn_1_instruction_id_list"])
        kwargs = [json.loads(k) for k in json.loads(row["turn_1_kwargs"])]
        if len(instruction_ids) != len(kwargs):
            issues.add("malformed", f"{len(instruction_ids)} instructions, {len(kwargs)} kwargs", id_, lang)
            continue
        if lang == "it" and re.search(r"\binglese\b", message["content"], re.I):
            # translation artefact ("plain English" -> "inglese semplice"): the prompt may push the answer to English
            issues.add("italian_prompt_mentions_english", message["content"][:160], id_, lang)
        flags = {}
        if stripped_quotes:
            flags.update(outer_quotes_removed=True, source_prompt_original=original)
            n_stripped += 1
        if lang == "it" and id_ in IT_REPAIRS:
            flags.update(repaired=True, source_prompt_original=original)
        elif lang == "it" and id_ in IT_PROBLEMS:
            flags[IT_PROBLEMS[id_][0]] = True
            issues.add(*IT_PROBLEMS[id_], id_, lang)
        if id_ in BOTH_PROBLEMS:
            flags[BOTH_PROBLEMS[id_][0]] = True
            issues.add(*BOTH_PROBLEMS[id_], id_, lang)
        items[lang].append(
            Item(
                id=id_,
                lang=lang,
                messages=[message],
                answer=None,
                scorer="ifeval",
                meta={
                    "instruction_id_list": instruction_ids,
                    "kwargs": kwargs,
                    "source_key": row["key"],
                    "turn": 1,
                    "template": "none",
                    **flags,
                },
            )
        )
    issues.add("outer_quotes_removed", f"{n_stripped} Italian prompts were wrapped whole in double quotes (no English prompt is); the outer pair was removed. Inner quotes are untouched; originals in meta.source_prompt_original.", lang="it")
    shared = {i.id for i in items["it"]} & {i.id for i in items["en"]}
    for lang_items in items.values():  # the shared ids: `multi_if`, what the suite runs
        for item in lang_items:
            item.meta["default"] = item.id in shared
    norm = lambda s: " ".join(s.lower().split())
    for lang_items in items.values():  # the text the repeat checker expects must be in the prompt (often after the instruction)
        for item in lang_items:
            for iid, kw in zip(item.meta["instruction_id_list"], item.meta["kwargs"]):
                if iid == "combination:repeat_prompt" and norm(kw["prompt_to_repeat"]) not in norm(item.messages[0]["content"]):
                    issues.add("repeat_text_missing", "the text the checker expects to be repeated is not in the prompt", item.id, item.lang)
    return Built(
        items,
        issues,
        {
            "name": "Multi-IF (turn 1)",
            "source": source(REPO) + " (multiIF_20241018.csv)",
            "paper": "He et al., 2024, Multi-IF: Benchmarking LLMs on Multi-Turn and Multilingual Instructions Following (arXiv:2410.15553)",
            "licence": "CC BY-NC 2.0 (data); checker code Apache 2.0",
            "scorer": "ifeval: Multi-IF's instruction checkers (vendored), strict and loose",
            "notes": [
                "Turn 1 only: the prompt is `turn_1_prompt`, checked against `turn_1_instruction_id_list` / `turn_1_kwargs`. No suffix is added.",
                "Ids are the source key without the language (`multiif-{prompt}-{variant}`); the English file has 909 rows and the Italian 493, so only the shared ids are parallel. The suite runs the 492 shared ids in both languages (`multi_if`; meta.default): the 417 English-only items bring instruction types the Italian file lacks (change case, response language, more keyword checks), and multiif-3691-2 has no English twin. Every item is in `multi_if_full`, off in the suite.",
                "How the checkers behave on Italian text is described in reports/multi_if_language.md.",
                "Prompt-checker consistency (2026-10-15): every checker argument (counts, keywords, end phrases, text to repeat) was looked up in its prompt, and every argument-free instruction (no commas, title, JSON, quotes...) was looked for in the wording. Count conversions like 'at most 150 words' checked as 'fewer than 151' are correct. Real problems, Italian only: 4 prompts drop an instruction the checker still applies (multiif-1922-5, -1922-9, -288-9: the 'repeat the request' instruction; multiif-3245-3: 'no commas, 2 placeholders'), 1 keyword differs from its checker (multiif-2662-10). Two more (multiif-2716-1, -8: 'use il at most once') were nearly impossible in Italian because the checker counted 'il' inside any word; fixed by the checker change below. Both languages: multiif-337-3 and -15 ask for 400 words but check for 336 (lenient). REPAIRED (2026-10-15): the 4 dropped instructions are restored with our Italian translation of the English sentence, and multiif-2662-10 now asks for the keyword its checker tests ('impegna'); meta.repaired, original prompt in meta.source_prompt_original. The 400/336 pair is flagged, not edited.",
                "Outer quotes (2026-10-15): 127 Italian prompts, and no English one, were wrapped whole in a pair of double quotes, a translation artefact. It made the prompts read as quoted text and could fail the 'repeat the request' checker (which expects the text without quotes). The outer pair is removed; inner quotes are kept; meta.outer_quotes_removed, original in meta.source_prompt_original.",
                "Checker change (2026-10-15, both languages): keywords:existence and keywords:frequency match whole words (Unicode-aware; punctuation and elided articles are boundaries; keywords taken literally), where Multi-IF searches substrings with a regex. It concerns 61 Italian and 137 English instructions; on those, scores are not identical to Multi-IF's reference code. Marked in src/scorers/vendor/multi_if_ifeval.py.",
            ],
        },
    )


@register("multi_if")
def build_shared() -> Built:
    return subset(build(), lambda i: i.meta["default"], "Multi-IF (turn 1, shared ids)",
                  "What the suite runs (2026-11-02): the 492 ids in both languages, with identical instruction lists. Every item (493 / 909) is `multi_if_full`, off in the suite.")
