"""Batch evaluation over all sample tasks.

For each task we:
1. run the agent to produce a solution,
2. on success, re-run the solution against the *hidden* tests,
3. collect pass/fail, retries-used, and final workflow state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agent import run_agent  # noqa: E402
from agent.tools import run_tests  # noqa: E402

load_dotenv()

TASKS_PATH = Path(__file__).resolve().parent.parent / "tasks" / "sample_tasks.json"


def main() -> int:
    tasks = json.loads(TASKS_PATH.read_text())
    rows = []
    for task in tasks:
        final = run_agent(task, max_retries=3)
        public_ok = final["workflow"] == "Done"
        hidden_ok = False
        if public_ok and task.get("hidden_tests"):
            hidden = run_tests(final["code"], task["hidden_tests"])
            hidden_ok = hidden["passed"]
        rows.append({
            "task": task["name"],
            "public_passed": public_ok,
            "hidden_passed": hidden_ok,
            "retries": final["retries"],
            "workflow": final["workflow"],
        })

    # Pretty-print.
    print(f"{'task':<20} {'public':<8} {'hidden':<8} {'retries':<8} state")
    for r in rows:
        print(
            f"{r['task']:<20} "
            f"{'yes' if r['public_passed'] else 'no':<8} "
            f"{'yes' if r['hidden_passed'] else 'no':<8} "
            f"{r['retries']:<8} {r['workflow']}"
        )
    pub = sum(1 for r in rows if r["public_passed"])
    hid = sum(1 for r in rows if r["hidden_passed"])
    print(f"\nSummary: {pub}/{len(rows)} public, {hid}/{len(rows)} hidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
