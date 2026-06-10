"""Batch evaluation over all sample tasks."""
from __future__ import annotations

import json
import sys
import argparse
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agent import run_agent  # noqa: E402
from agent.tools import run_tests  # noqa: E402

load_dotenv()

TASKS_PATH = Path(__file__).resolve().parent.parent / "tasks" / "sample_tasks.json"


def run_once(task: dict, spec_mode: str) -> dict:
    start = time.perf_counter()
    final = run_agent(task, spec_mode=spec_mode)
    elapsed = time.perf_counter() - start
    spec_result = final.get("spec_result") or {}
    spec_ok = bool(spec_result.get("passed"))
    code_ok = final["workflow"] == "Done"
    hidden_ok = False
    if code_ok and task.get("hidden_tests"):
        hidden_ok = run_tests(final.get("code", ""), task["hidden_tests"])["passed"]
    return {
        "task": task["name"],
        "mode": final.get("spec_mode", spec_mode),
        "spec": spec_ok,
        "code": code_ok,
        "hidden": hidden_ok,
        "states": spec_result.get("states_found"),
        "seconds": elapsed,
        "spec_retries": final.get("spec_retries", 0),
        "code_retries": final.get("code_retries", 0),
        "workflow": final["workflow"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-mode", choices=["example", "specification"], default="example")
    parser.add_argument(
        "--compare-spec-modes",
        action="store_true",
        help="Run each task once with both example and specification modes.",
    )
    args = parser.parse_args()

    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    rows = []
    modes = ["example", "specification"] if args.compare_spec_modes else [args.spec_mode]
    for task in tasks:
        for mode in modes:
            rows.append(run_once(task, mode))

    print(
        f"{'task':<20} {'mode':<14} {'spec':<6} {'code':<6} {'hidden':<8} "
        f"{'states':<7} {'sec':<7} {'sret':<5} {'cret':<5} state"
    )
    for row in rows:
        print(
            f"{row['task']:<20} "
            f"{row['mode']:<14} "
            f"{'yes' if row['spec'] else 'no':<6} "
            f"{'yes' if row['code'] else 'no':<6} "
            f"{'yes' if row['hidden'] else 'no':<8} "
            f"{str(row['states']):<7} "
            f"{row['seconds']:<7.2f} "
            f"{row['spec_retries']:<5} "
            f"{row['code_retries']:<5} {row['workflow']}"
        )

    spec_count = sum(1 for row in rows if row["spec"])
    code_count = sum(1 for row in rows if row["code"])
    print(f"\nSummary: {spec_count}/{len(rows)} spec, {code_count}/{len(rows)} code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
