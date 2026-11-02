"""Per-output trace statistics: format, loops, language, length.

Adapted from trace_criteria (our separate trace-analysis project: validity.py format and loop checks, language.py
English-word measure, preprocess.py masking), with its default thresholds; kept here so the harness
does not depend on that project. Markers are left out on purpose.

- format: the first problem of the output, or None: `truncated` (finish_reason length),
  `unclosed_think`, `bad_delimiters` (not exactly one opening and one closing delimiter, in order),
  `empty_thinking`, `empty_answer`, `replacement_char` (U+FFFD: bytes lost in decoding),
  `native_think_in_answer` (another model's thinking tags, e.g. Magistral's [THINK], in the answer).
- loops: `loop_status` names the triggers, joined by "+": `dup_4gram` (more than half of the
  thinking's word 4-grams occur more than once), `step_repeat` (a paragraph of 40+ characters
  repeated more than 3 times; code paragraphs are skipped, since a model rewriting its function
  while checking it is not looping), `tail_loop` (the last 512 words of the output are one sequence of
  at most 64 words, repeated). It tells a model stuck in a loop until the token cap from one that
  was still reasoning when cut off. Steps are paragraphs (blank-line separated); trace_criteria
  also avoids splitting inside code or LaTeX.
  Known false positive: a short line restated while re-reading the problem (Qwen3-8B on a 2x2 Zebra
  puzzle repeated a 41-character category line 4 times); raise MIN_STEP_CHARS if it becomes common.
- language (non-English prompts only): share of English words in the thinking (a word is English
  if common in English and much rarer in the prompt's language, wordfreq Zipf gap; words copied
  from the prompt, code, LaTeX, numbers and capitalised words are skipped), the number of
  paragraphs of thinking that are mostly English, how often the thinking switches between
  English and non-English paragraphs, and `lang_ok` (no mostly-English paragraph). The same
  measure on the answer gives `answer_mostly_en` (None for answers too short to judge), which
  matters for free-text benchmarks (Multi-IF, X-AlpacaEval).
- `trace_ok`: format ok, no loop, and `lang_ok` not False (trace_criteria's `pass`, minus
  correctness, which the scorers report).
- length: thinking in model tokens (from generation) and in whitespace words, which compare
  across languages without the tokenizer's bias (Italian takes more tokens per word).
"""

import re
from collections import Counter
from functools import lru_cache

# --- masking (trace_criteria/preprocess.py) ---
MASK_RE = re.compile(
    r"""
    (?P<code>```.*?(?:```|\Z) | `[^`\n]+`)
  | (?P<latex>
        \\begin\{(?P<env>[^}]+)\}.*?\\end\{(?P=env)\}
      | \$\$.*?\$\$
      | \\\[.*?\\\]
      | \\\(.*?\\\)
      | (?<![\\$])\$(?!\s)[^$\n]*?(?<![\s\\])\$(?!\d)
    )
  | (?P<url>https?://\S+)
  | (?P<markdown>
        ^[ \t]*(?:\#{1,6}|[-*+]|>|\d+[.)])[ \t]+
      | ^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$
      | \*{1,3} | _{2,} | ~~ | \|
    )
  | (?P<number>(?<![\w.,])[-+]?\d+(?:[.,]\d+)*%?(?!\w))
    """,
    re.VERBOSE | re.DOTALL | re.MULTILINE,
)

# --- language (trace_criteria/language.py and config.yaml `en_words`) ---
WORD_RE = re.compile(r"[^\W\d_]+")
CODE_LIKE_RE = re.compile(r"[_=/\\<>{}\[\]()]|\w\.\w|[a-z][A-Z]")
CODE_LINE_RE = re.compile(
    r"^\s*(?:def|class|if|elif|else|for|while|return|import|from|try|except|with|raise|assert|print|var|let|const"
    r"|function|public|private|static|void|SELECT|FROM|WHERE)\b"
    r"|\w\s*[=!]=\s*\S|\]\s?[-+*/]?=\s?\S|->|=>|[A-Za-z_]\w*\s?=\s?[\w\"'\[({]|\w\([^()]*\)\s*[:{]\s*$|;\s*$|^\s*[}\])]"
)
EDGE_PUNCT = "\"'“”‘’«»`.,;:!?()[]{}*"
PARAGRAPH_RE = re.compile(r"\n\s*\n")
MIN_EN_ZIPF, MIN_GAP, MIN_CHARS = 3.0, 1.5, 2
PARAGRAPH_MIN_WORDS, PARAGRAPH_MIN_RATE = 8, 0.5


def mask(text: str) -> str:
    return MASK_RE.sub(" ", text)


def candidate_words(text: str) -> list[str]:
    words = []
    for line in text.splitlines():
        if CODE_LINE_RE.search(line):
            continue
        for chunk in line.split():
            chunk = chunk.strip(EDGE_PUNCT)
            if not chunk or CODE_LIKE_RE.search(chunk):
                continue
            words += [w.lower() for w in WORD_RE.findall(chunk) if not w[0].isupper()]
    return words


@lru_cache(maxsize=200_000)
def is_english_word(word: str, language: str) -> bool:
    from wordfreq import zipf_frequency

    if len(word) < MIN_CHARS:
        return False
    en = zipf_frequency(word, "en")
    return en >= MIN_EN_ZIPF and en - zipf_frequency(word, language) >= MIN_GAP


def english_in_thinking(thinking: str, prompt: str, language: str) -> dict:
    ignore = set(candidate_words(prompt))
    n_words = n_english = 0
    labels = []  # per paragraph long enough to judge: True if mostly English
    for paragraph in PARAGRAPH_RE.split(mask(thinking)):
        words = [w for w in candidate_words(paragraph) if w not in ignore]
        if not words:
            continue
        english = sum(is_english_word(w, language) for w in words)
        n_words, n_english = n_words + len(words), n_english + english
        if len(words) >= PARAGRAPH_MIN_WORDS:
            labels.append(english >= PARAGRAPH_MIN_RATE * len(words))
    return {
        "think_en_word_rate": n_english / n_words if n_words else None,
        "think_paragraphs": len(labels),
        "think_en_paragraphs": sum(labels),
        "think_lang_switches": sum(a != b for a, b in zip(labels, labels[1:])),  # paragraph to paragraph, either way
        "lang_ok": not any(labels),  # trace_criteria's LNG_pass: no mostly-English paragraph
        "checked_words": n_words,
    }


def english_in_answer(answer: str, prompt: str, language: str) -> dict:
    """The same measure on the final answer. Judged only when the answer has at least
    PARAGRAPH_MIN_WORDS checkable words: a number, a letter or a code block says nothing."""
    m = english_in_thinking(answer, prompt, language)
    judged = m["checked_words"] >= PARAGRAPH_MIN_WORDS
    return {
        "answer_en_word_rate": m["think_en_word_rate"] if judged else None,
        "answer_mostly_en": (m["think_en_word_rate"] >= PARAGRAPH_MIN_RATE) if judged else None,
    }


# --- format (trace_criteria/validity.py) ---
def format_status(row: dict, delims: list[str]) -> str | None:
    if row["finish_reason"] == "length":
        return "truncated"
    if not row["think_closed"]:
        return "unclosed_think"
    completion, (open_d, close_d) = row["completion"], delims
    if not (completion.count(open_d) == 1 and completion.count(close_d) == 1 and completion.find(open_d) < completion.find(close_d)):
        return "bad_delimiters"
    if not row["thinking"].strip():
        return "empty_thinking"
    if not row["answer"].strip():
        return "empty_answer"
    if "�" in completion:
        return "replacement_char"
    if any(tag in row["answer"] for tag in NATIVE_THINK_TAGS):
        return "native_think_in_answer"
    return None


# --- loops (trace_criteria/validity.py and config.yaml `loop`) ---
NATIVE_THINK_TAGS = ["[THINK]", "[/THINK]"]
DUP_4GRAM_MAX, STEP_REPEAT_MAX, MIN_STEP_CHARS = 0.5, 3, 40
TAIL_WORDS, MAX_PERIOD, MIN_REPEATS = 512, 64, 3


def dup_ngram_rate(words: list[str], n: int = 4) -> float | None:
    """Fraction of n-grams that occur more than once."""
    ngrams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not ngrams:
        return None
    counts = Counter(ngrams)
    return sum(counts[g] > 1 for g in ngrams) / len(ngrams)


def is_code(paragraph: str) -> bool:
    """A fenced block, a function or class (its docstring included), or a paragraph whose lines are mostly code."""
    lines = [line for line in paragraph.splitlines() if line.strip()]
    if "```" in paragraph or (lines and re.match(r"\s*(?:async\s+)?(?:def|class)\s+\w+.*:\s*$", lines[0])):
        return True
    return sum(bool(CODE_LINE_RE.search(line)) for line in lines) * 2 > len(lines)


def max_step_repeat(steps: list[str]) -> int | None:
    """Max occurrences of any normalised step of at least MIN_STEP_CHARS characters, code left out."""
    steps = [s for s in steps if not is_code(s)]
    counts = Counter(s for s in (re.sub(r"\s+", " ", s.lower()).strip() for s in steps) if len(s) >= MIN_STEP_CHARS)
    return max(counts.values()) if counts else None


def tail_loop(words: list[str]) -> bool:
    """The last TAIL_WORDS words repeat one sequence of at most MAX_PERIOD words."""
    tail = words[-TAIL_WORDS:]
    for period in range(1, MAX_PERIOD + 1):
        if len(tail) < period * MIN_REPEATS:
            break
        if all(tail[i] == tail[i - period] for i in range(period, len(tail))):
            return True
    return False


def loop_check(thinking: str, answer: str) -> dict:
    dup = dup_ngram_rate(thinking.lower().split())
    repeat = max_step_repeat(PARAGRAPH_RE.split(thinking))
    triggers = [
        name
        for name, hit in (
            ("dup_4gram", dup is not None and dup > DUP_4GRAM_MAX),
            ("step_repeat", repeat is not None and repeat > STEP_REPEAT_MAX),
            ("tail_loop", tail_loop((thinking + "\n" + answer).split())),  # loops at the end of either
        )
        if hit
    ]
    return {"loop": bool(triggers), "loop_status": "+".join(triggers) or None, "dup_4gram_rate": dup}


def trace_stats(row: dict, delims: list[str]) -> dict:
    status = format_status(row, delims)
    out = {
        "format_ok": status is None,
        "format_status": status,
        **loop_check(row["thinking"], row["answer"]),
        "think_tokens": row["tokens"]["thinking"],
        "think_words": len(row["thinking"].split()),
    }
    if row["language"] != "en":
        thinking = english_in_thinking(row["thinking"], row["prompt"], row["language"])
        thinking.pop("checked_words")
        out.update(thinking, **english_in_answer(row["answer"], row["prompt"], row["language"]))
    # trace_criteria's `pass` without correctness (scored separately); English outputs have no language flag
    out["trace_ok"] = out["format_ok"] and not out["loop"] and out.get("lang_ok", True)
    return out
