"""Scorers that compare an extracted answer with the gold: math, MCQ, exact match, grid."""

import json
import logging
import re
import unicodedata

# math_verify warns on every call that its (signal-based) timeout is off; we turn it
# off on purpose, see parse_math
logging.getLogger("math_verify").setLevel(logging.ERROR)


# --- math_verify ------------------------------------------------------------

def last_boxed(text: str) -> str | None:
    """Content of the last \\boxed{...} (or \\fbox{...}), with balanced braces."""
    starts = [m.end() for m in re.finditer(r"\\(?:boxed|fbox)\s*\{", text)]
    for start in reversed(starts):
        depth = 1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i].strip()
    return None


def parse_math(expr: str):
    from math_verify import parse

    # parsing_timeout=None: math_verify's timeout uses signals, which only work in the main thread
    return parse(expr if "$" in expr else f"${expr}$", parsing_timeout=None)


def score_math_verify(item: dict, answer: str) -> dict:
    from math_verify import verify

    extracted = last_boxed(answer)
    if extracted is None:
        return {"correct": False, "extracted": None, "reason": "no_boxed"}
    candidate = extracted
    if item["meta"].get("decimal_comma") and re.fullmatch(r"-?\d+,\d+", candidate.strip()):
        candidate = candidate.replace(",", ".")  # "6,12" -> "6.12" (numeric INVALSI items only)
    gold = parse_math(str(item["answer"]))
    pred = parse_math(candidate)
    if not gold:
        return {"correct": False, "extracted": extracted, "reason": "gold_unparsed"}
    return {"correct": bool(verify(gold, pred, timeout_seconds=None)), "extracted": extracted}


# --- mcq ----------------------------------------------------------------------

ANSWER_CUE = r"(?:risposta(?:\s+(?:corretta|finale|esatta))?|answer|final answer|correct answer)"


def extract_choice(answer: str, choices: list[str]) -> str | None:
    """The option letter the answer commits to, or None.

    Tried in order: the last "Risposta: X" / "Answer: X"; the last \\boxed{X};
    an answer that is nothing but the letter. Anything else is not guessed.
    """
    letters = "".join(re.escape(c) for c in choices)
    # tolerate markdown and brackets around the letter: **Risposta:** (B)
    cue = re.findall(rf"{ANSWER_CUE}\s*(?:è|is)?\s*[:：]?\s*[*_\s]*[\(\[]?\s*([{letters}])\b(?![a-zà-ù])", answer, flags=re.I)
    if cue:
        return cue[-1].upper()
    boxed = last_boxed(answer)
    if boxed is not None:
        m = re.fullmatch(rf"(?:\\text\{{)?\s*\(?([{letters}])\)?\s*\}}?\.?", boxed.strip(), flags=re.I)
        if m:
            return m.group(1).upper()
    bare = re.fullmatch(rf"[*_\s\(\[]*([{letters}])[\)\]*_\s.]*", answer.strip(), flags=re.I)
    return bare.group(1).upper() if bare else None


def score_mcq(item: dict, answer: str) -> dict:
    extracted = extract_choice(answer, item["meta"]["choices"])
    return {"correct": extracted == item["answer"], "extracted": extracted}


# --- exact_match --------------------------------------------------------------

def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().strip()
    text = text.strip("\"'“”«»*_ .")
    text = re.sub(r"\s*,\s*", ",", text)
    return re.sub(r"\s+", " ", text)


def extract_integer(answer: str) -> tuple[str | None, str]:
    """AIW: the first integer within 100 characters after the last answer marker ("### Answer:",
    "### Risposta:", "Final Answer:"), even on the next lines; else the integer of a final
    \\boxed{}. Returns (integer, how it was found)."""
    cues = list(re.finditer(rf"{ANSWER_CUE}\s*[:：]", answer, flags=re.I))
    if cues:
        number = re.search(r"-?\d+", answer[cues[-1].end(): cues[-1].end() + 100])
        if number:
            return number.group(0), "answer_marker"
    boxed = last_boxed(answer)
    if boxed is not None and re.fullmatch(r"\s*-?\d+\s*", boxed):
        return boxed.strip(), "boxed"
    return None, "none"


def score_exact_match(item: dict, answer: str) -> dict:
    if item["meta"].get("integer"):
        extracted, how = extract_integer(answer)
        return {"correct": extracted == str(item["answer"]).strip(), "extracted": extracted, "found_by": how}
    cue = re.findall(rf"{ANSWER_CUE}\s*[:：]\s*(.+)", answer, flags=re.I)
    extracted = cue[-1].strip() if cue else None
    if extracted is None:
        return {"correct": False, "extracted": None, "reason": "no_answer_cue"}
    return {"correct": normalise(extracted) == normalise(str(item["answer"])), "extracted": extracted}


# --- grid_match ---------------------------------------------------------------

def last_json_object(text: str):
    """The last top-level {...} in `text` that parses as JSON."""
    ends = [i for i, c in enumerate(text) if c == "}"]
    for end in reversed(ends):
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : end + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(obj, dict):
                        return obj
                    break
    return None


def _cell(value) -> str:
    if isinstance(value, list):  # ZeroEval accepts a one-element list for a cell
        value = value[0] if value else ""
    return str(value).strip().casefold()


def score_grid_match(item: dict, answer: str) -> dict:
    """Exact grid match, plus cell accuracy.

    zebralogic: gold {"House 1": {"Name": ...}}, prediction under "solution".
    multizebra: gold {"object_1": [attributes]}, compared as a set per object
    (MultiZebraLogic's own rule: order inside an object does not matter).
    `off_list` (multizebra): the answer has a value that is in none of the puzzle's lists, e.g.
    an English word in an Italian answer. Every listed value is in the gold exactly once, so the
    gold values are the lists.
    """
    gold = item["answer"]
    obj = last_json_object(answer)
    if obj is None:
        return {"correct": False, "parsed": False, "cell_accuracy": 0.0}
    if item["meta"].get("format") == "multizebra":
        total = sum(len(v) for v in gold.values())
        right = 0
        for key, attributes in gold.items():
            predicted = obj.get(key)
            predicted = {_cell(a) for a in predicted} if isinstance(predicted, list) else set()
            right += len({_cell(a) for a in attributes} & predicted)
        exact = all(
            isinstance(obj.get(k), list) and {_cell(a) for a in obj[k]} == {_cell(a) for a in v} and len(obj[k]) == len(v)
            for k, v in gold.items()
        )
        listed = {_cell(a) for attributes in gold.values() for a in attributes}
        values = [a for v in obj.values() if isinstance(v, list) for a in v]
        off_list = any(_cell(a) not in listed for a in values)
        return {"correct": exact, "parsed": True, "cell_accuracy": right / total, "off_list": off_list}
    solution = obj.get("solution", obj)
    if not isinstance(solution, dict):
        return {"correct": False, "parsed": False, "cell_accuracy": 0.0}
    total = right = 0
    for house, row in gold.items():
        predicted = solution.get(house)
        for column, value in row.items():
            total += 1
            if isinstance(predicted, dict) and column in predicted and _cell(predicted[column]) == _cell(value):
                right += 1
    return {"correct": right == total, "parsed": True, "cell_accuracy": right / total}
