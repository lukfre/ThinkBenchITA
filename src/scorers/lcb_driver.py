"""Runs INSIDE the sandbox: checks solution.py against tests.json (LiveCodeBench rules).

Functional tests call Solution().<func_name>(*args), each argument being one
JSON line of the test input. Stdin tests run solution.py as a program and
compare stdout line by line (exact after stripping, or numerically equal).
Stops at the first failing test and writes result.json.
"""

import json
import signal
import subprocess
import sys
from decimal import Decimal, InvalidOperation

sys.set_int_max_str_digits(0)
sys.setrecursionlimit(10**6)

PREAMBLE = (
    "from string import *\nfrom re import *\nfrom datetime import *\nfrom collections import *\n"
    "from heapq import *\nfrom bisect import *\nfrom copy import *\nfrom math import *\nfrom random import *\n"
    "from statistics import *\nfrom itertools import *\nfrom functools import *\nfrom operator import *\n"
    "from io import *\nfrom sys import *\nfrom json import *\nfrom builtins import *\nfrom typing import *\n"
    "import string\nimport re\nimport datetime\nimport collections\nimport heapq\nimport bisect\nimport copy\n"
    "import math\nimport random\nimport statistics\nimport itertools\nimport functools\nimport operator\n"
    "import io\nimport sys\nimport json\nsys.setrecursionlimit(50000)\n"
)  # LiveCodeBench's import_string: solutions are written assuming these names exist


def same_output(got: str, expected: str) -> bool:
    got_lines = [line.strip() for line in got.strip().splitlines()]
    exp_lines = [line.strip() for line in expected.strip().splitlines()]
    if len(got_lines) != len(exp_lines):
        return False
    for g, e in zip(got_lines, exp_lines):
        if g == e:
            continue
        try:
            if [Decimal(x) for x in g.split()] != [Decimal(x) for x in e.split()]:
                return False
        except InvalidOperation:
            return False
    return True


class TestTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise TestTimeout()


def main():
    spec = json.load(open("tests.json"))
    tests, per_test = spec["tests"], spec["timeout_per_test"]
    code = open("solution.py", encoding="utf-8").read()
    result = {"passed": False, "n_tests": len(tests), "n_run": 0, "failure": None}

    def finish():
        json.dump(result, open("result.json", "w"))
        sys.exit(0)

    functional = tests and tests[0]["testtype"] == "functional"
    if functional:
        namespace = {"__name__": "__solution__"}
        try:
            exec(compile(PREAMBLE + code, "solution.py", "exec"), namespace)
            method = getattr(namespace["Solution"](), spec["func_name"])
        except BaseException as e:  # noqa: BLE001 - model code may raise anything
            result["failure"] = {"kind": "load_error", "detail": repr(e)[:500]}
            finish()
        signal.signal(signal.SIGALRM, _alarm)
    else:
        with open("program.py", "w", encoding="utf-8") as f:
            f.write(PREAMBLE + code)

    for n, test in enumerate(tests):
        result["n_run"] = n + 1
        if functional:
            try:
                args = [json.loads(line) for line in test["input"].split("\n")]
                expected = json.loads(test["output"])
                signal.alarm(per_test)
                try:
                    got = method(*args)
                finally:
                    signal.alarm(0)
                if isinstance(got, tuple):
                    got = list(got)
                ok = got == expected
                detail = None if ok else "wrong_answer"
            except TestTimeout:
                ok, detail = False, "timeout"
            except BaseException as e:  # noqa: BLE001
                ok, detail = False, "runtime_error: " + repr(e)[:300]
        else:
            try:
                run = subprocess.run([sys.executable, "-I", "program.py"], input=test["input"], capture_output=True, text=True, timeout=per_test)
                if run.returncode != 0:
                    ok, detail = False, "runtime_error: " + run.stderr[-300:]
                else:
                    ok = same_output(run.stdout, test["output"])
                    detail = None if ok else "wrong_answer"
            except subprocess.TimeoutExpired:
                ok, detail = False, "timeout"
        if not ok:
            result["failure"] = {"kind": detail.split(":")[0], "detail": detail, "test_index": n}
            finish()
    result["passed"] = True
    finish()


if __name__ == "__main__":
    main()
