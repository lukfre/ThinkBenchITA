import json

import pytest

from src.split import split_completion
from src.metrics import pass_at_k, summarise
from src.scorers import sandbox, score
from src.scorers.answers import extract_choice, last_boxed, last_json_object
from src.scorers.code_exec import decode_private_tests, extract_code


def item(scorer, answer=None, **meta):
    return {"id": "x", "lang": "it", "messages": [], "answer": answer, "scorer": scorer, "meta": meta}


# --- thinking / answer split ---

def test_split_closed_block():
    assert split_completion("<think>\nragiono\n</think>\n\nRisposta: B", ["<think>", "</think>"]) == ("ragiono", "Risposta: B", True)


def test_split_truncated_thinking_has_empty_answer():
    assert split_completion("<think>\nragiono ancora", ["<think>", "</think>"]) == ("ragiono ancora", "", False)


def test_split_without_delimiters_is_all_answer():
    assert split_completion("42", ["<think>", "</think>"]) == ("", "42", False)


# --- math ---

def test_last_boxed_nested_and_last():
    assert last_boxed(r"prima \boxed{1} poi \boxed{\frac{1}{2}}") == r"\frac{1}{2}"
    assert last_boxed("nessuna") is None


@pytest.mark.parametrize(
    "gold,answer,ok",
    [
        (r"$\frac{\pi}{3}$", r"Quindi \boxed{\pi/3}", True),
        ("204", r"\boxed{204}", True),
        ("204", r"\boxed{205}", False),
        ("204", "La risposta è 204", False),  # no \boxed: not scored as correct
        (r"\sqrt{51}", r"$$\boxed{\sqrt{51}}$$", True),
        (r"336^\circ", r"\boxed{336}", True),
    ],
)
def test_math_verify(gold, answer, ok):
    assert score(item("math_verify", gold), answer)["correct"] is ok


def test_math_decimal_comma_only_when_flagged():
    assert score(item("math_verify", "6.12", decimal_comma=True), r"\boxed{6,12}")["correct"] is True
    assert score(item("math_verify", "6.12"), r"\boxed{6,12}")["correct"] is False


# --- mcq ---

@pytest.mark.parametrize(
    "answer,expected",
    [
        ("Risposta: B", "B"),
        ("**Risposta:** (C)", "C"),
        ("Answer: A\n\nWait. Answer: D", "D"),
        (r"\boxed{B}", "B"),
        ("B", "B"),
        ("La risposta è B", "B"),
        ("Risposta: Bisogna calcolare", None),  # a word, not a letter
        ("Credo che A o B siano plausibili", None),
        ("... so B is wrong. Therefore, the answer is (C).", "C"),  # Olmo 3 GPQA format
        ("Quindi, la risposta è (D)", "D"),
        ("Quindi, la risposta è D.", "D"),
    ],
)
def test_extract_choice(answer, expected):
    assert extract_choice(answer, ["A", "B", "C", "D"]) == expected


def test_true_false():
    it = item("mcq", "F", choices=["V", "F"])
    assert score(it, "Risposta: F")["correct"] is True
    assert score(it, "Risposta: V")["correct"] is False


def test_exact_match_normalises():
    it = item("exact_match", "minore, rossa")
    assert score(it, 'Risposta: "Minore,  rossa".')["correct"] is True
    assert score(it, "minore, rossa")["correct"] is False  # no cue


# --- grid ---

def test_last_json_object_takes_the_last_valid_one():
    assert last_json_object('x {"a": 1} y {"b": {"c": 2}} z') == {"b": {"c": 2}}
    assert last_json_object("no json {broken") is None


def test_grid_match_zebralogic():
    gold = {"House 1": {"Name": "Arnold", "Drink": "tea"}, "House 2": {"Name": "Peter", "Drink": "water"}}
    it = item("grid_match", gold, format="zebralogic")
    good = json.dumps({"reasoning": "...", "solution": {"House 1": {"Name": "arnold", "Drink": "Tea"}, "House 2": {"Name": "Peter", "Drink": "water"}}})
    bad = good.replace("water", "milk")
    assert score(it, good) == {"correct": True, "parsed": True, "cell_accuracy": 1.0}
    assert score(it, bad)["correct"] is False and score(it, bad)["cell_accuracy"] == 0.75
    assert score(it, "non lo so")["parsed"] is False


def test_grid_match_multizebra_ignores_order_within_an_object():
    it = item("grid_match", {"object_1": ["Italia", "gatto"], "object_2": ["Francia", "cane"]}, format="multizebra")
    assert score(it, '{"object_1": ["gatto", "Italia"], "object_2": ["Francia", "cane"]}')["correct"] is True
    assert score(it, '{"object_1": ["Francia", "cane"], "object_2": ["Italia", "gatto"]}')["correct"] is False



def test_grid_match_multizebra_flags_values_outside_the_lists():
    it = item("grid_match", {"casa_1": ["Italia", "gatto"], "casa_2": ["Francia", "cane"]}, format="multizebra")
    right = score(it, '{"casa_1": ["Italia", "Gatto"], "casa_2": ["Francia", "cane"]}')
    swapped = score(it, '{"casa_1": ["Francia", "cane"], "casa_2": ["Italia", "gatto"]}')
    english = score(it, '{"casa_1": ["Italy", "cat"], "casa_2": ["Francia", "cane"]}')
    assert right["off_list"] is False and swapped["off_list"] is False  # wrong, but every value is listed
    assert english["off_list"] is True and english["correct"] is False

# --- ifeval ---

def test_ifeval_strict_and_loose():
    it = item("ifeval", instruction_id_list=["punctuation:no_comma", "startend:quotation"], kwargs=[{}, {}])
    assert score(it, '"Ciao a tutti"')["correct"] is True
    out = score(it, 'Ecco la risposta:\n"Ciao a tutti"')
    assert out["correct"] is False and out["correct_loose"] is True
    assert score(it, '"Ciao, a tutti"')["follow_strict"] == [False, True]


def test_ifeval_keywords_are_whole_words():
    freq = lambda kw, rel, n: item("ifeval", instruction_id_list=["keywords:frequency"], kwargs=[{"keyword": kw, "relation": rel, "frequency": n}])
    exist = lambda kws: item("ifeval", instruction_id_list=["keywords:existence"], kwargs=[{"keywords": kws}])
    # 'il' inside possibile/simile/utile does not count; the article does, in any case
    assert score(freq("il", "less than", 2), "È possibile, simile e utile: il gatto dorme.")["correct"] is True
    assert score(freq("il", "less than", 2), "Il gatto e il cane.")["correct"] is False
    assert score(freq("the", "less than", 2), "There, other mothers bathe the cat.")["correct"] is True
    # punctuation, elision and accents are boundaries; phrases still work; no regex surprises
    assert score(exist(["impegno"]), "Con l'impegno, si vince.")["correct"] is True
    assert score(exist(["città"]), "Amo la città!")["correct"] is True
    assert score(exist(["cat"]), "A category of things")["correct"] is False
    assert score(exist(["go for"]), "Let's go for it")["correct"] is True
    assert score(exist(["c++"]), "I write C++ daily")["correct"] is True


# --- code ---

def test_extract_code_prefers_last_python_block():
    answer = "```python\nx = 1\n```\ntesto\n```python\nx = 2\n```\n```text\nnote\n```"
    assert extract_code(answer) == ("x = 2\n", True)
    assert extract_code("x = 3") == ("x = 3", False)


def test_private_tests_refuse_pickled_code():
    import base64, pickle, zlib

    ok = base64.b64encode(zlib.compress(pickle.dumps(json.dumps([{"input": "1", "output": "1", "testtype": "stdin"}])))).decode()
    assert decode_private_tests(ok)[0]["input"] == "1"
    evil = base64.b64encode(zlib.compress(pickle.dumps(print))).decode()
    with pytest.raises(pickle.UnpicklingError):
        decode_private_tests(evil)


needs_bwrap = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap not installed")
HE = dict(test_format="humaneval", entry_point="add", source_prompt="def add(a, b):\n", test="def check(candidate):\n    assert candidate(1, 2) == 3\n")


@needs_bwrap
def test_code_exec_humaneval_pass_fail_and_body_only():
    assert score(item("code_exec", **HE), "```python\ndef add(a, b):\n    return a + b\n```")["status"] == "passed"
    assert score(item("code_exec", **HE), "```python\ndef add(a, b):\n    return a - b\n```")["status"] == "failed"
    assert score(item("code_exec", **HE), "```python\n    return a + b\n```")["correct"] is True


@needs_bwrap
def test_sandbox_blocks_network_home_and_runaway_code():
    from pathlib import Path

    from src.schema import ROOT

    # only the interpreter and the venv are mounted: no source tree, no data, no HF token or ssh keys
    hidden = [ROOT / "src", ROOT / "data", Path.home() / ".cache", Path.home() / ".ssh"]
    probe = (
        "import os, socket\n"
        "try:\n    socket.create_connection(('1.1.1.1', 53), 2); print('NET')\n"
        "except OSError:\n    print('nonet')\n"
        f"print(sum(os.path.exists(p) for p in {[str(p) for p in hidden]!r}))\n"
        "import numpy; print('numpy')\n"
    )
    run = sandbox.run_python({"p.py": probe}, "p.py")
    assert run.stdout.split() == ["nonet", "0", "numpy"], run.stderr
    loop = sandbox.run_python({"p.py": "while True: pass"}, "p.py", sandbox.Limits(timeout=1))
    assert loop.timed_out
    hog = sandbox.run_python({"p.py": "x = bytearray(2 * 2**30)"}, "p.py", sandbox.Limits(memory_mb=512))
    assert hog.returncode != 0


LCB_FUNC = dict(
    test_format="livecodebench", func_name="twice", private_tests_ref={"repo": "r", "file": "f", "question_id": "q"},
    public_tests=[{"input": "[1, 2]\n3", "output": "[2, 4, 3]", "testtype": "functional"}],
)
LCB_STDIN = dict(
    test_format="livecodebench", func_name=None, private_tests_ref={"repo": "r", "file": "f", "question_id": "q"},
    public_tests=[{"input": "2 3\n", "output": "5\n", "testtype": "stdin"}],
)


@needs_bwrap
def test_code_exec_livecodebench(monkeypatch):
    from src.scorers import code_exec

    monkeypatch.setattr(code_exec, "private_tests", lambda *a: [{"input": "[]\n0", "output": "[0]", "testtype": "functional"}])
    good = "```python\nclass Solution:\n    def twice(self, xs: List[int], k: int) -> List[int]:\n        return [2 * x for x in xs] + [k]\n```"
    assert score(item("code_exec", **LCB_FUNC), good)["correct"] is True
    wrong = score(item("code_exec", **LCB_FUNC), good.replace("2 * x", "3 * x"))
    assert wrong["correct"] is False and wrong["failure"]["kind"] == "wrong_answer"
    forged = "```python\nimport json\njson.dump({'passed': True, 'n_tests': 1, 'n_run': 1}, open('result.json', 'w'))\nraise SystemExit\n```"
    assert score(item("code_exec", **LCB_FUNC), forged)["correct"] is False

    monkeypatch.setattr(code_exec, "private_tests", lambda *a: [{"input": "10 -4\n", "output": "6", "testtype": "stdin"}])
    program = "```python\na, b = map(int, input().split())\nprint(a + b)\n```"
    assert score(item("code_exec", **LCB_STDIN), program)["correct"] is True
    slow = score(item("code_exec", **LCB_STDIN), "```python\nwhile True: pass\n```")
    assert slow["correct"] is False and slow["failure"]["kind"] == "timeout"


# --- metrics ---

def test_pass_at_k():
    assert pass_at_k(10, 0, 1) == 0
    assert pass_at_k(10, 3, 1) == pytest.approx(0.3)
    assert pass_at_k(4, 1, 2) == pytest.approx(0.5)
    assert pass_at_k(4, 3, 2) == 1
    with pytest.raises(ValueError):
        pass_at_k(2, 1, 5)


def test_summarise():
    def row(pid, correct, finish="stop"):
        return {"prompt_id": pid, "score": {"correct": correct}, "finish_reason": finish, "think_closed": True, "answer": "a", "tokens": {"thinking": 10}, "meta": {}}

    out = summarise([row("a", True), row("a", False), row("b", False), row("b", False, "length")], [1, 2, 5])
    assert out["pass@1"] == pytest.approx(0.25) and out["pass@2"] == pytest.approx(0.5) and "pass@5" not in out
    assert out["truncated_rate"] == 0.25


# --- judge ---

def test_judge_alpacaeval_preference_and_prompt():
    import math

    from src import judge

    # P("m") read from top log-probabilities, as AlpacaEval's logprob_parser does
    assert judge.p_first({"m": math.log(0.75), "M": math.log(0.25), "x": math.log(0.1)}) == pytest.approx(0.75)
    assert judge.p_first({" M": 0.0}) == 0.0 and judge.p_first({"no": 0.0}) is None
    # AlpacaEval scale: 2 = model preferred; flips with the position of the model output
    assert judge.preference(0.75, model_is_first=True) == pytest.approx(1.75)
    assert judge.preference(0.75, model_is_first=False) == pytest.approx(1.25)
    assert judge.preference(None, True) is None
    # seeded random position: stable per item, roughly balanced
    firsts = [judge.model_first(f"run:xalpaca:it:{i}#0", 20261015) for i in range(1000)]
    assert firsts == [judge.model_first(f"run:xalpaca:it:{i}#0", 20261015) for i in range(1000)] and 400 < sum(firsts) < 600
    for lang in ("en", "it"):
        m = judge.judge_messages(lang, "ISTR-X", "OUT-1", "OUT-2")
        text = m[1]["content"]
        assert text.index("ISTR-X") < text.index("OUT-1") < text.index("OUT-2") and '"model_identifier": "M"' in text
    assert judge.prompt_hash("it") != judge.prompt_hash("en")
