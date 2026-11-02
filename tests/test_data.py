"""Checks on the built data files. Skipped for benchmarks that have not been built
(run `uv run python prepare.py` first; gated sources need Hub access)."""

import pytest

from src.loaders import LOADERS
from src.schema import DATA_DIR, SCORERS, read_jsonl

EXPECTED = {  # benchmark -> (it, en) item counts at the pinned revisions
    "polymath": (500, 500), "mclm_math100": (99, 99), "mclm_aime2024": (30, 30), "aime25": (30, 30),
    "invalsi_mate": (420, None), "humaneval": (164, 164), "humaneval_mhe": (164, None), "mbppplus": (378, 378), "livecodebench": (612, 612),
    "multi_if": (492, 492), "multi_if_full": (493, 909), "aiw": (30, 30), "xalpaca": (805, 805), "gpqa": (197, 197), "gpqa_main": (448, 448), "zebra": (None, 1000), "zebra_gen": (500, 500),
}  # fmt: skip
PARALLEL = ["aiw", "polymath", "mclm_math100", "mclm_aime2024", "aime25", "humaneval", "mbppplus", "livecodebench", "xalpaca", "gpqa", "gpqa_main", "multi_if", "zebra_gen"]


def rows(benchmark, lang):
    path = DATA_DIR / benchmark / f"{lang}.jsonl"
    if not path.exists():
        pytest.skip(f"{benchmark}/{lang} not built")
    return read_jsonl(path)


def test_every_benchmark_of_the_instructions_has_a_loader():
    assert set(EXPECTED) <= set(LOADERS)


@pytest.mark.parametrize("benchmark", sorted(EXPECTED))
def test_schema_and_counts(benchmark):
    for lang, expected in zip(("it", "en"), EXPECTED[benchmark]):
        if expected is None:
            assert not (DATA_DIR / benchmark / f"{lang}.jsonl").exists()
            continue
        items = rows(benchmark, lang)
        assert len(items) == expected
        assert len({i["id"] for i in items}) == len(items)
        for i in items:
            assert set(i) == {"id", "lang", "messages", "answer", "scorer", "meta"}
            assert i["lang"] == lang and i["scorer"] in SCORERS
            if i["messages"] is None:
                assert i["meta"]["pending_translation"] is True
            else:
                assert i["messages"][-1]["role"] == "user" and i["messages"][-1]["content"].strip()


@pytest.mark.parametrize("benchmark", PARALLEL)
def test_parallel_ids_scorers_and_gold(benchmark):
    it = {i["id"]: i for i in rows(benchmark, "it")}
    en = {i["id"]: i for i in rows(benchmark, "en")}
    assert set(it) == set(en)
    for id_, item in it.items():
        assert item["scorer"] == en[id_]["scorer"]
        if benchmark == "zebra_gen":  # gold values are words of each language; compare the config indices
            assert item["meta"]["cells"] == en[id_]["meta"]["cells"]
        else:
            assert item["answer"] == en[id_]["answer"]  # same gold in both languages


def test_source_text_is_embedded_verbatim():
    for benchmark in ("polymath", "mclm_math100"):
        for lang in ("it", "en"):
            for i in rows(benchmark, lang):
                assert i["messages"][0]["content"].startswith(i["meta"]["source_prompt"])
                if i["meta"].get("figure_restored_from_english"):
                    assert i["meta"]["source_prompt"].startswith(i["meta"]["source_prompt_original"].rstrip())
    for benchmark in ("aime25", "mclm_aime2024"):  # MathArena's instruction comes first
        for lang in ("it", "en"):
            for i in rows(benchmark, lang):
                assert i["messages"][0]["content"].endswith("\n\n" + i["meta"]["source_prompt"])
    for i in rows("multi_if", "it") + rows("xalpaca", "it"):
        assert len(i["messages"]) == 1  # no template at all


def test_aime25_matharena_prompt():
    for lang, first in (("en", "Put your final answer"), ("it", "Scrivi la tua risposta finale")):
        for i in rows("aime25", lang):
            assert i["messages"][0]["content"].startswith(first)
            assert i["messages"][0]["content"].endswith(i["meta"]["source_prompt"])
            assert i["messages"] is not None


def test_polymath_default_levels():
    items = rows("polymath", "it")
    on = {i["meta"]["level"] for i in items if i["meta"]["default"]}
    assert on == {"medium", "high"} and sum(i["meta"]["default"] for i in items) == 222
    assert not any(i["meta"]["default"] for i in items if "also_in" in i["meta"])  # AIME twins are scored in the AIME benchmarks


def test_polymath_repaired_golds_accept_correct_answers():
    from src.scorers import score

    items = {i["id"]: i for i in rows("polymath", "en")}
    correct = {
        "polymath-medium-036": r"\boxed{[\frac{b_1 q^m-2b_1}{m},\frac{b_1q^m}{m}]}",
        "polymath-medium-111": r"\boxed{\frac{\ln(3+2\sqrt{2})}{2\sqrt{2}}}",
        "polymath-top-050": r"\boxed{2^{2^1}, 2^{2^2}, 2^{2^4}, 2^{2^8}}",
        "polymath-top-093": r"\boxed{f(x)=x^2 \text{ and } f(x)=0}",
    }
    for id_, answer in correct.items():
        assert items[id_]["meta"]["gold_repaired"] and score(items[id_], answer)["correct"], id_
    assert not score(items["polymath-top-050"], r"\boxed{4, 16, 65536}")["correct"]


def test_invalsi_is_diagnostic_and_typed():
    items = rows("invalsi_mate", "it")
    assert all(i["meta"]["diagnostic"] is True for i in items)
    by_type = {t: {i["scorer"] for i in items if i["meta"]["type"] == t} for t in {i["meta"]["type"] for i in items}}
    assert by_type == {"multipla": {"mcq"}, "vero/falso": {"mcq"}, "numero": {"mcq"}, "completa frase": {"exact_match"}}
    assert sum(i["meta"]["official"] for i in items) == 400 and sum(i["meta"]["default"] for i in items) == 397
    for i in items:
        if i["meta"]["type"] == "numero":
            options = i["meta"]["options"]
            assert options["ABCD".index(i["answer"])] == i["meta"]["gold_value"]
            assert all(f"{l}. {o}" in i["messages"][0]["content"] for l, o in zip("ABCD", options))


def test_gpqa_same_permutation_and_canary():
    it = {i["id"]: i for i in rows("gpqa_main", "it")}
    en = {i["id"]: i for i in rows("gpqa_main", "en")}
    for id_ in it:
        assert it[id_]["meta"]["permutation"] == en[id_]["meta"]["permutation"]
        assert it[id_]["meta"]["is_diamond"] == en[id_]["meta"]["is_diamond"]
        assert it[id_]["meta"]["canary"] and en[id_]["meta"]["canary"]
        assert en[id_]["meta"]["options"][en[id_]["meta"]["permutation"].index(0)] == en[id_]["meta"]["source_prompt"]["correct_answer"]
    assert sum(i["meta"]["is_diamond"] for i in en.values()) == 198
    assert len({i["answer"] for i in en.values()}) == 4  # gold letters are spread, not all "A"


def test_gpqa_same_option_under_same_letter():
    """After realignment, the numbers in each option must match across languages (where options have numbers)."""
    import re

    sig = lambda s: tuple(x.replace(",", ".") for x in re.findall(r"\d+(?:[.,]\d+)?", s))
    it = {i["id"]: i for i in rows("gpqa_main", "it")}
    en = {i["id"]: i for i in rows("gpqa_main", "en")}
    checked = mismatched = 0
    for id_, item in it.items():
        e, i = [sig(o) for o in en[id_]["meta"]["options"]], [sig(o) for o in item["meta"]["options"]]
        if len(set(e)) == 4 and all(e):
            checked += 1
            mismatched += e != i
    assert checked > 150 and mismatched <= 2  # 2 items reword a number in one option


def test_gpqa_olmo3_prompt_and_flags():
    for lang, phrase in (("en", "Therefore, the answer is (ANSWER_LETTER)"), ("it", "Quindi, la risposta è (LETTERA_RISPOSTA)")):
        items = rows("gpqa_main", lang)
        for i in items:
            content = i["messages"][0]["content"]
            assert content.count(phrase) == 2 and content.endswith("(C), (D).")
            assert all(f" ({l}) {o}\n" in content for l, o in zip("ABCD", i["meta"]["options"]))
        assert {i["id"] for i in items if i["meta"].get("gold_duplicated")} == {"gpqa-recDjE01bu72pPUU2", "gpqa-recoiTJPGUmzAkief"}
        assert {i["id"] for i in items if not i["meta"]["default"]} == {"gpqa-recDjE01bu72pPUU2", "gpqa-recoiTJPGUmzAkief"}
        diamond = {i["id"] for i in rows("gpqa", lang)}
        assert diamond == {i["id"] for i in items if i["meta"]["is_diamond"] and i["meta"]["default"]} and len(diamond) == 197


def test_gpqa_permutation_is_stable():
    from src.loaders.gpqa import permutation

    assert permutation("rec123") == permutation("rec123")
    assert sorted(permutation("rec123")) == [0, 1, 2, 3]


def test_aiw_parse_italian_and_scoring():
    from src.loaders.aiw import parse, render_en, solve
    from src.scorers import score

    en = {i["id"]: i for i in rows("aiw", "en")}
    it = {i["id"]: i for i in rows("aiw", "it")}
    assert len({i["meta"]["subset"] for i in en.values()}) == 5
    for id_, item in en.items():
        parts = parse(item["messages"][0]["content"])
        assert render_en(parts) == item["messages"][0]["content"].replace("\u2019", "'") and solve(parts) == int(item["answer"])
        assert "### Risposta:" in it[id_]["messages"][0]["content"] and "Answer" not in it[id_]["messages"][0]["content"]
    assert "fratelli maschi" in it["aiw-light-family-v1"]["messages"][0]["content"]
    assert "fratelli e sorelle" in it["aiw-light-siblings-v1"]["messages"][0]["content"]
    item = it["aiw-main-v3-standard"]  # gold 5
    assert score(item, "Ragionamento...\n### Risposta: 5")["correct"] and score(item, "**### Answer: 5 sorelle**")["correct"]
    assert score(item, "### Final Answer:\n\n$$\n\\boxed{5}\n$$")["correct"]  # answer on the next lines
    assert score(item, "So the answer is \\boxed{5}")["found_by"] == "boxed"
    assert not score(item, "### Risposta: 4")["correct"] and not score(item, "La risposta è 5")["correct"]


def test_zebra_gen_gold_scores_itself_and_covers_zebralogic_sizes():
    import collections
    import json

    from src.scorers.answers import score_grid_match

    for lang in ("it", "en"):
        items = rows("zebra_gen", lang)
        sizes = collections.Counter(i["meta"]["size"] for i in items)
        assert len(sizes) == 25 and set(sizes.values()) == {20}
        classes = collections.Counter(i["meta"]["size_class"] for i in items)
        assert classes == {"small": 160, "medium": 140, "large": 100, "xlarge": 100}
        for i in items:
            assert score_grid_match(i, json.dumps(i["answer"])) == {"correct": True, "parsed": True, "cell_accuracy": 1.0, "off_list": False}


def test_code_benchmarks_italian_side_is_our_checked_translation():
    from src.scorers.code_exec import map_output_words

    for benchmark in ("humaneval", "mbppplus", "livecodebench"):
        it, en = rows(benchmark, "it"), {i["id"]: i for i in rows(benchmark, "en")}
        assert all(i["messages"] for i in it), benchmark
        for i in it:
            assert set(en[i["id"]]["meta"]) <= set(i["meta"]), "the Italian meta must hold every English field (one schema per config)"
            assert i["meta"]["source_prompt_en"] == en[i["id"]]["meta"]["source_prompt"]
            assert i["meta"]["source_prompt"] != i["meta"]["source_prompt_en"]
    for i in rows("livecodebench", "it"):
        assert "⟦" not in i["meta"]["source_prompt"]
        if i["meta"].get("output_word_map"):  # samples in the statement use the Italian words, as the mapped tests
            lines = {line.strip() for line in i["meta"]["source_prompt"].splitlines()}
            for t in i["meta"]["public_tests"]:
                if t["testtype"] == "stdin":
                    assert all(x.strip() in lines for x in map_output_words(t["output"], i["meta"]["output_word_map"]).splitlines() if x.strip())
