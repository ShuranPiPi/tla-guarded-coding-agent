"""Sandbox-ish test runner.

The generated code is executed in a **separate Python subprocess** with a
hard timeout. We do not claim real sandboxing — this is a course prototype,
not a production judge — but subprocess + timeout + no network side-effects is
enough to stop accidental infinite loops from hanging the agent.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import List

from .state import TestResult

RUNNER_TEMPLATE = """\
import sys, traceback

{code}

{tests}

print("ALL_TESTS_PASSED")
"""


def run_tests(code: str, tests: List[str], timeout: float = 10.0) -> TestResult:
    """Run `code` then `tests` in a fresh subprocess, return a TestResult."""
    test_block = "\n".join(tests)
    program = RUNNER_TEMPLATE.format(code=code, tests=test_block)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "solution.py"
        path.write_text(program)
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            return TestResult(
                passed=False,
                stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
                stderr=f"TimeoutExpired after {timeout}s",
                failing_test="<timeout>",
            )

    passed = proc.returncode == 0 and "ALL_TESTS_PASSED" in proc.stdout
    failing = None
    if not passed:
        # Best-effort: pull the first assert line out of the traceback.
        for line in (proc.stderr or "").splitlines():
            line = line.strip()
            if line.startswith("assert ") or "AssertionError" in line:
                failing = line
                break
    return TestResult(
        passed=passed,
        stdout=proc.stdout,
        stderr=proc.stderr,
        failing_test=failing,
    )


if __name__ == "__main__":  # pragma: no cover — manual smoke test
    code = "def add(a, b):\n    return a + b\n"
    tests = ["assert add(2, 3) == 5", "assert add(-1, 1) == 0"]
    print(run_tests(code, tests))
