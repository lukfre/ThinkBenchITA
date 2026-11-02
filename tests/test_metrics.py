import json

from src import metrics
from src.run_report import write_run_report
from src.trace_stats import trace_stats


def output(lang, i, correct, finish="stop"):
    thinking = "Allora, provo con il caso semplice e controllo la somma." if lang == "it" else "So, let me try the simple case and check the sum."
    row = {"trace_id": f"r:b:{lang}:{i}#0", "prompt_id": str(i), "language": lang, "prompt": "?", "completion": f"<think>{thinking}</think>42",
           "thinking": thinking, "answer": "42" if finish == "stop" else "", "think_closed": finish == "stop", "finish_reason": finish,
           "gold": "42", "sample_idx": 0, "tokens": {"thinking": 12}, "score": {"correct": correct}}
    row["trace"] = trace_stats(row, ["<think>", "</think>"])
    return row


def test_run_report_lists_both_languages_and_outputs_to_read(tmp_path):
    rows = {"it": [output("it", 0, True), output("it", 1, False), output("it", 2, False, "length")],
            "en": [output("en", 0, True), output("en", 1, True), output("en", 2, False, "length")]}
    all_metrics = {"b": {}}
    for lang, rs in rows.items():
        (tmp_path / "b").mkdir(exist_ok=True)
        (tmp_path / "b" / f"{lang}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs))
        all_metrics["b"][lang] = {"overall": metrics.summarise(rs, [1])}
    all_metrics["b"]["it"]["length_vs_en"] = metrics.length_ratio_vs_en(rows["it"], rows["en"])
    write_run_report(tmp_path, all_metrics, "some/model")
    report = (tmp_path / "report.md").read_text()
    assert "| b | 33.3 | 66.7 | -33.3 |" in report
    assert report.count("<summary>wrong:") == 1 and report.count("<summary>truncated:") == 2


def test_shards_cover_every_item_once_and_child_command_drops_gpus_and_stage():
    import run_eval

    items = [{"id": str(i)} for i in range(11)]
    shards = [run_eval.shard_items("aime25", "it", items, s, 3) for s in range(3)]
    assert sorted(i["id"] for shard in shards for i in shard) == sorted(i["id"] for i in items)
    assert max(map(len, shards)) - min(map(len, shards)) <= 1
    assert run_eval.child_argv(["--run", "x", "--gpus", "0", "1", "--stage", "all", "--limit", "3"]) == ["--run", "x", "--limit", "3"]
    assert run_eval.child_argv(["--gpus=0,1", "--run=x"]) == ["--run=x"]


def test_resume_finds_done_items_and_restores_item_order(tmp_path):
    import run_eval

    path = tmp_path / "b" / "it.jsonl"
    path.parent.mkdir()
    rows = [{"prompt_id": "2", "sample_idx": 1}, {"prompt_id": "2", "sample_idx": 0}, {"prompt_id": "0", "sample_idx": 0}]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert run_eval.done_ids(path, n=2) == {"2"}  # "0" has 1 of its 2 samples
    run_eval.sort_file(path, [{"id": str(i)} for i in range(3)])
    assert [(r["prompt_id"], r["sample_idx"]) for r in map(json.loads, path.read_text().splitlines())] == [("0", 0), ("2", 0), ("2", 1)]


def test_no_thinking_keeps_the_checks_and_drops_the_text():
    import run_eval

    row = output("it", 0, True)
    del row["trace"]
    run_eval.drop_thinking_text(row, ["<think>", "</think>"])
    assert row["thinking"] is None and row["completion"] is None and row["answer"] == "42"
    assert row["trace"]["format_ok"] is True and "think_en_word_rate" in row["trace"]
