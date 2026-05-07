"""End-to-end demo: run the agent on one sample task and print the trace."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Make ``agent`` importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from agent import run_agent  # noqa: E402

load_dotenv()

TASKS_PATH = Path(__file__).resolve().parent.parent / "tasks" / "sample_tasks.json"


def main(task_name: str = "two_sum") -> None:
    tasks = json.loads(TASKS_PATH.read_text())
    task = next((t for t in tasks if t["name"] == task_name), tasks[0])

    print(f"=== Running agent on task: {task['name']} ===\n")
    final = run_agent(task, max_retries=3)

    print("--- Trace ---")
    for line in final["history"]:
        print(" ", line)

    print("\n--- Final workflow state ---")
    print(" ", final["workflow"])
    print("\n--- Final code ---")
    print(final["code"])
    print("\n--- Retries used ---", final["retries"])


if __name__ == "__main__":
<<<<<<< HEAD
    main(sys.argv[1] if len(sys.argv) > 1 else "two_sum")
=======
    # main(sys.argv[1] if len(sys.argv) > 1 else "two_sum")
    main("column_maximim_strategy")
>>>>>>> 412f6f8 (20260507)
