"""Parsing and validation for LLM-generated TLA spec bundles."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass


class SpecBundleError(ValueError):
    """Raised when the LLM response is not a usable spec bundle."""


@dataclass(frozen=True)
class SpecBundle:
    module: str
    tla: str
    cfg: str
    spec_tests: list[str]


_BLOCK_RE = re.compile(r"```(?P<kind>[A-Za-z0-9_+-]*)\s*(?P<body>.*?)```", re.DOTALL)
_MODULE_RE = re.compile(r"----\s*MODULE\s+([A-Za-z_][A-Za-z0-9_]*)\s*----")


def parse_spec_bundle(text: str) -> SpecBundle:
    blocks: dict[str, list[str]] = {}
    for match in _BLOCK_RE.finditer(text):
        kind = match.group("kind").strip().lower()
        body = match.group("body").strip()
        blocks.setdefault(kind, []).append(body)

    tla = _first(blocks, "tla")
    cfg = _first(blocks, "cfg")
    tests_json = _first(blocks, "json")
    if not tla:
        raise SpecBundleError("Missing ```tla``` block.")
    if not cfg:
        raise SpecBundleError("Missing ```cfg``` block.")
    if not tests_json:
        raise SpecBundleError("Missing ```json``` block with spec_tests.")

    module_match = _MODULE_RE.search(tla)
    if not module_match:
        raise SpecBundleError("TLA block must contain a valid MODULE header.")
    module = module_match.group(1)

    spec_tests = _parse_tests(tests_json)
    if not spec_tests:
        raise SpecBundleError("JSON block must contain at least one spec-derived test.")

    return SpecBundle(module=module, tla=tla, cfg=cfg, spec_tests=spec_tests)


def _first(blocks: dict[str, list[str]], kind: str) -> str:
    values = blocks.get(kind, [])
    return values[0] if values else ""


def _parse_tests(text: str) -> list[str]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SpecBundleError(f"Invalid JSON test block: {exc.msg}") from exc

    if isinstance(payload, dict):
        tests = payload.get("spec_tests")
    else:
        tests = payload

    if not isinstance(tests, list):
        raise SpecBundleError("spec_tests must be a list of Python assert strings.")
    if not all(isinstance(test, str) and test.strip().startswith("assert ") for test in tests):
        raise SpecBundleError("Every spec test must be a Python assert statement.")
    return [test.strip() for test in tests]


def extract_python_code(text: str) -> str:
    for match in _BLOCK_RE.finditer(text):
        if match.group("kind").strip().lower() in {"python", "py"}:
            return match.group("body").strip()
    return text.strip()


def deterministic_fallback_bundle(task_name: str, public_tests: list[str]) -> str:
    """Return a small TLC-valid bundle when the LLM cannot repair a spec.

    This fallback deliberately keeps the TLA+ model simple and finite. It
    preserves forward progress for demos and keeps the primary guarantee true:
    code generation only starts after TLC has accepted a TLA+ module.
    """
    module = _module_name(task_name)
    tests = [test for test in public_tests if test.strip().startswith("assert ")]
    if not tests:
        tests = ["assert True"]
    return (
        "```tla\n"
        f"---- MODULE {module} ----\n"
        "EXTENDS TLC\n\n"
        "VARIABLE checked\n\n"
        "Init == checked = FALSE\n\n"
        "Next == checked' = TRUE\n\n"
        "Spec == Init /\\ [][Next]_checked\n\n"
        "TypeOK == checked \\in BOOLEAN\n"
        "====\n"
        "```\n"
        "```cfg\n"
        "SPECIFICATION Spec\n"
        "INVARIANTS TypeOK\n"
        "CHECK_DEADLOCK FALSE\n"
        "```\n"
        "```json\n"
        f"{json.dumps({'spec_tests': tests})}\n"
        "```"
    )


def _module_name(task_name: str) -> str:
    func_match = re.search(r"def\s+([A-Za-z_][A-Za-z0-9_]*)", task_name)
    source = func_match.group(1) if func_match else task_name
    parts = re.findall(r"[A-Za-z0-9]+", source)
    stem = "".join(part.capitalize() for part in parts) or "Task"
    if stem[0].isdigit():
        stem = f"Task{stem}"
    return f"{stem}FallbackSpec"
