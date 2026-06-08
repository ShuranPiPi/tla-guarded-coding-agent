"""Batch evaluation over all sample tasks."""
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
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    rows = []
    for task in tasks:
        final = run_agent(task)
        spec_result = final.get("spec_result") or {}
        spec_ok = bool(spec_result.get("passed"))
        code_ok = final["workflow"] == "Done"
        hidden_ok = False
        if code_ok and task.get("hidden_tests"):
            hidden_ok = run_tests(final.get("code", ""), task["hidden_tests"])["passed"]
        rows.append({
            "task": task["name"],
            "spec": spec_ok,
            "code": code_ok,
            "hidden": hidden_ok,
            "spec_retries": final.get("spec_retries", 0),
            "code_retries": final.get("code_retries", 0),
            "workflow": final["workflow"],
        })

    print(f"{'task':<20} {'spec':<6} {'code':<6} {'hidden':<8} {'sret':<5} {'cret':<5} state")
    for row in rows:
        print(
            f"{row['task']:<20} "
            f"{'yes' if row['spec'] else 'no':<6} "
            f"{'yes' if row['code'] else 'no':<6} "
            f"{'yes' if row['hidden'] else 'no':<8} "
            f"{row['spec_retries']:<5} "
            f"{row['code_retries']:<5} {row['workflow']}"
        )

    spec_count = sum(1 for row in rows if row["spec"])
    code_count = sum(1 for row in rows if row["code"])
    print(f"\nSummary: {spec_count}/{len(rows)} spec, {code_count}/{len(rows)} code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
