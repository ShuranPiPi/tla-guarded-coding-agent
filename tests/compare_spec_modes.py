"""Offline comparison of the two spec-generation modes.

This script does not call an LLM. It compares the deterministic bundles used by
the two prompt families, so the result is reproducible without API keys. Use
`tests/eval.py --compare-spec-modes` for live provider-backed runs.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.specs import deterministic_fallback_bundle, parse_spec_bundle  # noqa: E402
from agent.tlc import run_tlc  # noqa: E402
from agent.tlaps import run_tlaps  # noqa: E402

TASKS_PATH = Path(__file__).resolve().parent.parent / "tasks" / "sample_tasks.json"


def run_one(task: dict, mode: str) -> dict:
    raw = deterministic_fallback_bundle(task["signature"], task.get("public_tests", []), mode)
    bundle = parse_spec_bundle(raw)
    start = time.perf_counter()
    if mode == "specification":
        result = run_tlaps(bundle.module, bundle.tla)
        checker = "TLAPS"
        metric = result.obligations
    else:
        result = run_tlc(bundle.module, bundle.tla, bundle.cfg)
        checker = "TLC"
        metric = result.states_found
    elapsed = time.perf_counter() - start
    return {
        "task": task["name"],
        "mode": mode,
        "checker": checker,
        "passed": result.passed,
        "metric": metric,
        "seconds": elapsed,
        "module": bundle.module,
        "structured": bool(bundle.structured_spec),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    tasks = json.loads(TASKS_PATH.read_text(encoding="utf-8"))
    rows = []
    for _ in range(args.runs):
        for task in tasks:
            for mode in ("example", "specification"):
                rows.append(run_one(task, mode))

    print("| task | mode | checker | pass/runs | mean states/obligations | mean checker seconds | structured spec |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for task in tasks:
        for mode in ("example", "specification"):
            subset = [r for r in rows if r["task"] == task["name"] and r["mode"] == mode]
            passed = sum(1 for r in subset if r["passed"])
            metrics = [r["metric"] for r in subset if r["metric"] is not None]
            seconds = [r["seconds"] for r in subset]
            structured = any(r["structured"] for r in subset)
            print(
                f"| {task['name']} | {mode} | {subset[0]['checker']} | {passed}/{len(subset)} | "
                f"{statistics.mean(metrics):.1f} | {statistics.mean(seconds):.3f} | "
                f"{'yes' if structured else 'no'} |"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
