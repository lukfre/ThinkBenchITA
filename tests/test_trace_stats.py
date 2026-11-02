import pytest

from src.trace_stats import format_status, trace_stats

DELIMS = ["<think>", "</think>"]


def row(completion, thinking="ragiono", answer="42", closed=True, finish="stop", language="it", prompt="Quanto fa?"):
    return {"completion": completion, "thinking": thinking, "answer": answer, "think_closed": closed, "finish_reason": finish,
            "language": language, "prompt": prompt, "tokens": {"thinking": 3}}


@pytest.mark.parametrize(
    "r, expected",
    [
        (row("<think>\nragiono</think>42"), None),
        (row("<think>\nragiono", answer="", closed=False, finish="length"), "truncated"),
        (row("<think>\nragiono", answer="", closed=False), "unclosed_think"),
        (row("<think>\nragiono</think><think>ancora</think>42"), "bad_delimiters"),
        (row("<think>\n</think>42", thinking=""), "empty_thinking"),
        (row("<think>\nragiono</think>", answer=""), "empty_answer"),
    ],
)
def test_format_status(r, expected):
    assert format_status(r, DELIMS) == expected


def test_english_thinking_on_an_italian_prompt_is_detected():
    pytest.importorskip("wordfreq")
    en = "Okay, so I need to figure out which house the teacher lives in, and then check the other clues one by one."
    it = "Allora, devo capire in quale casa abita l'insegnante, e poi controllare gli altri indizi uno alla volta."
    s_en = trace_stats(row("", thinking=en), DELIMS)
    s_it = trace_stats(row("", thinking=it), DELIMS)
    assert s_en["think_en_word_rate"] > 0.5 and s_en["think_en_paragraphs"] == 1
    assert s_it["think_en_word_rate"] < 0.1 and s_it["think_en_paragraphs"] == 0
    assert "think_en_word_rate" not in trace_stats(row("", thinking=en, language="en"), DELIMS)


@pytest.mark.parametrize(
    "r, expected",
    [
        (row("<think>\nragiono</think>4�2", answer="4�2"), "replacement_char"),
        (row("<think>\nragiono</think>[THINK]altro[/THINK]42", answer="[THINK]altro[/THINK]42"), "native_think_in_answer"),
    ],
)
def test_format_status_lost_bytes_and_foreign_tags(r, expected):
    assert format_status(r, DELIMS) == expected


def test_loops():
    from src.trace_stats import loop_check

    reasoning = " ".join(f"passo {i}: considero il caso {i} e controllo che la somma sia {2 * i}." for i in range(200))
    assert loop_check(reasoning, "42")["loop"] is False
    stuck = reasoning + " " + "aspetta, ricontrollo. " * 300  # an ending stuck on one short sequence
    assert loop_check(stuck, "")["loop_status"] == "tail_loop"  # 600 repeated words in 3,400: under the 4-gram threshold
    assert loop_check("aspetta, ricontrollo. " * 300, "")["loop_status"] == "dup_4gram+tail_loop"
    paragraph = "Quindi la risposta dovrebbe essere 42, ma ricontrolliamo il calcolo."
    repeated = "\n\n".join([reasoning] + [paragraph, "Altro tentativo con numeri diversi."] * 4)
    assert loop_check(repeated, "42")["loop_status"] == "step_repeat"
    code = "def is_even(n):\n    return n % 2 == 0"
    rewritten = "\n\n".join([reasoning] + [x for i in range(5) for x in (code, f"Ricontrollo la funzione sul caso di test {i}.")])
    assert loop_check(rewritten, "")["loop"] is False  # a function rewritten while checking it
    with_docstring = 'def f(xs: list) -> list:\n    """Keep the integers.\n    >>> f(["a", 1])\n    [1]\n    """'
    assert loop_check(rewritten.replace(code, with_docstring), "")["loop"] is False
    assert loop_check(rewritten.replace(code, "suffix[i] = suffix[i + 1] + 1  # the next one"), "")["loop"] is False
    assert loop_check(rewritten.replace(code, paragraph), "")["loop_status"] == "step_repeat"


def test_language_flags_and_switches():
    pytest.importorskip("wordfreq")
    en = "Okay, so I need to figure out which house the teacher lives in, and then check the other clues one by one."
    it = "Allora, devo capire in quale casa abita l'insegnante, e poi controllare gli altri indizi uno alla volta."
    mixed = trace_stats(row("<think>x</think>42", thinking="\n\n".join([it, en, it])), DELIMS)
    assert mixed["think_lang_switches"] == 2 and mixed["lang_ok"] is False and mixed["trace_ok"] is False
    clean = trace_stats(row("<think>x</think>42", thinking=it), DELIMS)
    assert clean["think_lang_switches"] == 0 and clean["lang_ok"] is True and clean["trace_ok"] is True
    assert "lang_ok" not in trace_stats(row("<think>x</think>42", thinking=en, language="en"), DELIMS)


def test_answer_language_is_judged_only_on_long_answers():
    pytest.importorskip("wordfreq")
    en = "Here is the list you asked for, with a short note on each item and the reasons behind the order."
    it = "Ecco l'elenco che hai chiesto, con una breve nota su ogni voce e le ragioni dietro l'ordine."
    assert trace_stats(row("<think>x</think>a", answer=en), DELIMS)["answer_mostly_en"] is True
    assert trace_stats(row("<think>x</think>a", answer=it), DELIMS)["answer_mostly_en"] is False
    assert trace_stats(row("<think>x</think>42"), DELIMS)["answer_mostly_en"] is None
