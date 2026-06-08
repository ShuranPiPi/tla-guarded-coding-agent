"""Run the TLC-spec-guarded agent on one sample task and print the trace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agent import run_agent  # noqa: E402

load_dotenv()

TASKS_PATH = Path(__file__).resolve().parent.parent / "tasks" / "sample_tasks.json"


def main(task_name: str = "two_sum") -> None:
    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    task = next((t for t in tasks if t["name"] == task_name), tasks[0])

    print(f"=== Running spec-guarded agent on task: {task['name']} ===\n")
    final = run_agent(task)

    print("--- Trace ---")
    for line in final["history"]:
        print(" ", line)

    spec_result = final.get("spec_result") or {}
    print("\n--- Spec status ---")
    print(" ", "passed" if spec_result.get("passed") else "failed")
    print(" ", "module:", spec_result.get("module", ""))
    print(" ", "states:", spec_result.get("states_found"))
    if spec_result.get("error"):
        print(" ", "error:", spec_result["error"])

    print("\n--- Final workflow state ---")
    print(" ", final["workflow"])
    print(" ", final.get("terminal_reason", ""))
    print("\n--- Final code ---")
    print(final.get("code", ""))
    print("\n--- Retries used ---")
    print(" ", "spec:", final.get("spec_retries", 0), "code:", final.get("code_retries", 0))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "two_sum")
