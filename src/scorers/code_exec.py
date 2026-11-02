"""code_exec scorer: extract the model's code, run the benchmark tests in the sandbox.

Test formats (meta.test_format):
  humaneval      HumanEval+: `meta.test` defines check(candidate); run check(entry_point)
  script         MBPP+: `meta.test` is a script that calls the function by name
  livecodebench  public + private tests, functional or stdin (see lcb_driver.py)
"""

import base64
import io
import json
import pickle
import re
import zlib
from functools import lru_cache
from pathlib import Path

from ..schema import ROOT
from .sandbox import Limits, run_python

LIMITS = {"timeout": 60.0, "memory_mb": 4096, "lcb_timeout_per_test": 6, "lcb_timeout_total": 300.0}
DRIVER = (Path(__file__).parent / "lcb_driver.py").read_text(encoding="utf-8")
FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.S)


def extract_code(answer: str) -> tuple[str, bool]:
    """(code, fenced). The last ```python block, else the last fenced block,
    else the whole answer (which then usually fails to run, and is counted as such)."""
    blocks = FENCE.findall(answer)
    python = [body for lang, body in blocks if lang.lower() in ("python", "py", "python3")]
    if python:
        return python[-1], True
    if blocks:
        return blocks[-1][1], True
    return answer, False


# --- LiveCodeBench private tests -------------------------------------------------

class _NoGlobals(pickle.Unpickler):
    """The private tests are a pickled JSON *string*; refuse anything that would import code."""

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"refusing to load {module}.{name} from a test file")


def decode_private_tests(blob: str) -> list[dict]:
    try:
        return json.loads(blob)  # early releases stored plain JSON
    except json.JSONDecodeError:
        raw = zlib.decompress(base64.b64decode(blob.encode("utf-8")))
        return json.loads(_NoGlobals(io.BytesIO(raw)).load())


@lru_cache(maxsize=None)
def _offsets(repo: str, filename: str) -> tuple[Path, dict]:
    """question_id -> byte offset of its line in the Hub file (built once, cached on disk)."""
    from ..loaders import hf_file

    path = hf_file(repo, filename)
    cache = ROOT / ".cache" / "lcb_index" / f"{path.parent.parent.name}-{filename}.json"
    if cache.exists():
        return path, json.loads(cache.read_text())
    index, offset = {}, 0
    with open(path, "rb") as f:
        for line in f:
            head = line[:4096].decode("utf-8", "replace")
            match = re.search(r'"question_id":\s*"([^"]+)"', head) or re.search(r'"question_id":\s*"([^"]+)"', line.decode("utf-8"))
            index[match.group(1)] = offset
            offset += len(line)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(index))
    return path, index


@lru_cache(maxsize=2)
def private_tests(repo: str, filename: str, question_id: str) -> list[dict]:
    path, index = _offsets(repo, filename)
    with open(path, "rb") as f:
        f.seek(index[question_id])
        row = json.loads(f.readline())
    assert row["question_id"] == question_id
    return decode_private_tests(row["private_test_cases"])


# --- scorer ------------------------------------------------------------------------

def map_output_words(text: str, word_map: dict[str, str]) -> str:
    """Replace whole output words (Yes -> Sì); identity entries are skipped."""
    changed = {w: it for w, it in word_map.items() if w != it}
    if not changed:
        return text
    pattern = re.compile(r"(?<!\w)(" + "|".join(map(re.escape, sorted(changed, key=len, reverse=True))) + r")(?!\w)")
    return pattern.sub(lambda m: changed[m.group(1)], text)


def _result(run, passed: bool, fenced: bool, **extra) -> dict:
    status = "passed" if passed else "timeout" if run.timed_out else extra.pop("status", "failed")
    return {"correct": passed, "status": status, "fenced": fenced, "stderr": "" if passed else run.stderr[-600:], **extra}


def score_code_exec(item: dict, answer: str) -> dict:
    meta = item["meta"]
    code, fenced = extract_code(answer)
    fmt = meta["test_format"]
    if fmt == "humaneval":
        if not re.search(rf"^\s*def\s+{re.escape(meta['entry_point'])}\s*\(", code, re.M):
            # the model returned only the body: put it under the original signature
            code = meta["source_prompt"] + "\n" + code
        program = f"{code}\n\n{meta['test']}\n\ncheck({meta['entry_point']})\n"
        run = run_python({"prog.py": program}, "prog.py", Limits(LIMITS["timeout"], LIMITS["memory_mb"]))
        return _result(run, run.returncode == 0, fenced)
    if fmt == "script":
        imports = "\n".join(meta.get("test_imports") or [])
        program = f"{imports}\n{code}\n\n{meta['test']}\n"
        run = run_python({"prog.py": program}, "prog.py", Limits(LIMITS["timeout"], LIMITS["memory_mb"]))
        return _result(run, run.returncode == 0, fenced)
    if fmt == "livecodebench":
        ref = meta["private_tests_ref"]
        tests = list(meta["public_tests"]) + private_tests(ref["repo"], ref["file"], ref["question_id"])
        if meta.get("output_word_map"):  # Italian items: the program must print the Italian words (Yes -> Sì)
            tests = [{**t, "output": map_output_words(t["output"], meta["output_word_map"])} for t in tests]
        spec = {"tests": tests, "func_name": meta.get("func_name"), "timeout_per_test": LIMITS["lcb_timeout_per_test"]}
        total = min(LIMITS["lcb_timeout_total"], LIMITS["lcb_timeout_per_test"] * len(tests) + 10)
        run = run_python(
            {"solution.py": code, "tests.json": json.dumps(spec), "driver.py": DRIVER},
            "driver.py",
            Limits(total, LIMITS["memory_mb"]),
            collect=("result.json",),
        )
        try:
            result = json.loads(run.outputs["result.json"])
        except (KeyError, json.JSONDecodeError):
            return _result(run, False, fenced, status="crashed", n_tests=len(tests))
        # the driver shares /work with the solution, so a solution could write result.json
        # itself; only a result that accounts for every test is accepted
        passed = result.get("passed") is True and result.get("n_run") == len(tests) and result.get("n_tests") == len(tests)
        return _result(run, passed, fenced, n_tests=len(tests), failure=result.get("failure"))
    raise ValueError(f"unknown test_format {fmt!r}")
