"""LangGraph nodes for the TLC-spec-guarded coding agent."""
from __future__ import annotations

import os
from typing import Literal

from .llm import LLMClient, LLMUnavailableError, fallback_provider
from .rag import format_for_prompt, retrieve_fixes
from .specs import (
    SpecBundleError,
    deterministic_fallback_bundle,
    extract_python_code,
    parse_spec_bundle,
)
from .state import AgentState, SpecResult, TestResult
from .tlc import run_tlc
from .tools import run_tests


SPEC_SYS = (
    "You write small, finite TLA+ specifications that TLC can model-check. "
    "Output exactly three fenced blocks: ```tla```, ```cfg```, and ```json```. "
    "Do not use PlusCal, TLAPS, Reals, or unbounded sets. Prefer finite example "
    "constants and simple terminating state machines. The JSON block must be an "
    "object with a spec_tests list of Python assert strings for the required function."
)

SPEC_PROMPT = """\
Problem:
{problem}

Required Python signature:
{signature}

Public tests for context only:
{public_tests}

Generate a TLC-checkable TLA+ module and cfg. The TLA+ module should capture a
finite abstraction of the problem or its examples and include at least one
invariant or temporal property in the cfg. Then generate Python assert tests
derived from that finite spec.

Use this output shape exactly:
```tla
---- MODULE ExampleSpec ----
EXTENDS Naturals, Integers, Sequences, TLC
...
====
```
```cfg
SPECIFICATION Spec
INVARIANTS TypeOK
CHECK_DEADLOCK FALSE
```
```json
{{"spec_tests": ["assert ..."]}}
```
"""

SPEC_REPAIR_SYS = (
    "You repair TLA+ specs so TLC can check them. Preserve the task intent, "
    "but prioritize producing a syntactically valid, finite, TLC-checkable "
    "TLA+ module, cfg, and JSON spec_tests block."
)

CODE_SYS = (
    "You are a careful Python programmer. Produce a single, self-contained "
    "implementation of the requested function. Output only a ```python``` block."
)

CODE_REPAIR_SYS = (
    "You repair Python functions that failed tests. Use the traceback and any "
    "retrieved hints. Output only a corrected ```python``` block."
)


def init_node(state: AgentState) -> AgentState:
    return {
        "workflow": "GenerateSpec",
        "spec_retries": 0,
        "code_retries": 0,
        "max_spec_retries": state.get(
            "max_spec_retries", int(os.environ.get("AGENT_MAX_SPEC_RETRIES", "3"))
        ),
        "max_code_retries": state.get(
            "max_code_retries", int(os.environ.get("AGENT_MAX_CODE_RETRIES", "3"))
        ),
        "history": state.get("history", []) + ["Init -> GenerateSpec"],
    }


def generate_spec_node(state: AgentState) -> AgentState:
    prompt = SPEC_PROMPT.format(
        problem=state["problem"],
        signature=state["signature"],
        public_tests="\n".join(state.get("public_tests", [])) or "(none)",
    )
    try:
        resp = LLMClient().generate(SPEC_SYS, prompt)
        return {
            "spec_bundle_raw": resp.text,
            "provider_used": resp.provider,
            "workflow": "CheckSpec",
            "history": state.get("history", [])
            + [f"GenerateSpec -> CheckSpec ({resp.provider}:{resp.model})"],
        }
    except LLMUnavailableError as exc:
        return _spec_failure_update(state, str(exc), "GenerateSpec -> CheckSpec (provider unavailable)")


def check_spec_node(state: AgentState) -> AgentState:
    raw = state.get("spec_bundle_raw", "")
    try:
        bundle = parse_spec_bundle(raw)
    except SpecBundleError as exc:
        result: SpecResult = {
            "passed": False,
            "module": "",
            "stdout": "",
            "stderr": "",
            "error": f"Spec bundle parse failed: {exc}",
            "states_found": None,
        }
        return {
            "spec_result": result,
            "workflow": "CheckSpec",
            "history": state.get("history", []) + ["CheckSpec -> parse failed"],
        }

    tlc_result = run_tlc(bundle.module, bundle.tla, bundle.cfg)
    result = _spec_result_from_tlc(tlc_result)
    update: AgentState = {
        "spec_result": result,
        "workflow": "CheckSpec",
        "history": state.get("history", [])
        + [f"CheckSpec -> {'pass' if tlc_result.passed else 'fail'} ({bundle.module})"],
    }
    if tlc_result.passed:
        update.update({
            "tla_spec": bundle.tla,
            "tla_cfg": bundle.cfg,
            "spec_tests": bundle.spec_tests,
        })
    return update


def repair_spec_node(state: AgentState) -> AgentState:
    next_retry = state.get("spec_retries", 0) + 1
    if next_retry >= state.get("max_spec_retries", 3):
        return {
            "spec_bundle_raw": deterministic_fallback_bundle(
                state.get("signature", "Task"),
                state.get("public_tests", []),
            ),
            "spec_retries": next_retry,
            "workflow": "CheckSpec",
            "history": state.get("history", [])
            + [f"RepairSpec #{next_retry} -> CheckSpec (deterministic fallback)"],
        }

    provider = _repair_provider(state)
    prompt = (
        f"Problem:\n{state['problem']}\n\n"
        f"Required signature:\n{state['signature']}\n\n"
        f"Previous bundle:\n{state.get('spec_bundle_raw', '')}\n\n"
        f"TLC or parser error:\n{_spec_error(state)}\n\n"
        "Return a complete corrected bundle with ```tla```, ```cfg```, and ```json``` blocks."
    )
    try:
        resp = LLMClient(provider=provider).generate(SPEC_REPAIR_SYS, prompt)
        return {
            "spec_bundle_raw": resp.text,
            "provider_used": resp.provider,
            "spec_retries": next_retry,
            "workflow": "CheckSpec",
            "history": state.get("history", [])
            + [f"RepairSpec #{next_retry} -> CheckSpec ({resp.provider}:{resp.model})"],
        }
    except LLMUnavailableError as exc:
        return _spec_failure_update(state, str(exc), "RepairSpec -> CheckSpec (provider unavailable)")


def derive_tests_node(state: AgentState) -> AgentState:
    tests = state.get("spec_tests", [])
    return {
        "workflow": "GenerateCode",
        "history": state.get("history", []) + [f"DeriveTests -> GenerateCode ({len(tests)} tests)"],
    }


def generate_code_node(state: AgentState) -> AgentState:
    prompt = _code_prompt(state, previous_code="")
    try:
        resp = LLMClient().generate(CODE_SYS, prompt)
        return {
            "code": extract_python_code(resp.text),
            "provider_used": resp.provider,
            "workflow": "TestCode",
            "history": state.get("history", []) + [f"GenerateCode -> TestCode ({resp.provider}:{resp.model})"],
        }
    except LLMUnavailableError as exc:
        return {
            "code": "",
            "last_result": _test_failure(f"LLM unavailable: {exc}", "<generation>"),
            "workflow": "TestCode",
            "history": state.get("history", []) + ["GenerateCode -> TestCode (provider unavailable)"],
        }


def test_code_node(state: AgentState) -> AgentState:
    tests = state.get("spec_tests", [])
    result = run_tests(state.get("code", ""), tests) if tests else _test_failure("No spec tests", "<spec_tests>")
    return {
        "last_result": result,
        "workflow": "TestCode",
        "history": state.get("history", [])
        + [f"TestCode -> {'pass' if result['passed'] else 'fail'}"],
    }


def repair_code_node(state: AgentState) -> AgentState:
    err = state.get("last_result") or _test_failure("unknown failure", "<unknown>")
    query = (err.get("stderr") or "") + "\n" + (err.get("failing_test") or "")
    hits = retrieve_fixes(query, k=3)
    prompt = (
        _code_prompt(state, previous_code=state.get("code", ""))
        + f"\n\nTraceback / failure:\n{err.get('stderr', '')}\n"
        + f"Failing test:\n{err.get('failing_test', '')}\n"
        + f"Retrieved repair patterns:\n{format_for_prompt(hits)}\n"
    )
    try:
        resp = LLMClient().generate(CODE_REPAIR_SYS, prompt)
        return {
            "code": extract_python_code(resp.text),
            "provider_used": resp.provider,
            "code_retries": state.get("code_retries", 0) + 1,
            "workflow": "TestCode",
            "history": state.get("history", [])
            + [f"RepairCode #{state.get('code_retries', 0) + 1} -> TestCode ({resp.provider}:{resp.model})"],
        }
    except LLMUnavailableError as exc:
        return {
            "code_retries": state.get("code_retries", 0) + 1,
            "last_result": _test_failure(f"LLM unavailable: {exc}", "<repair>"),
            "workflow": "TestCode",
            "history": state.get("history", []) + ["RepairCode -> TestCode (provider unavailable)"],
        }


def done_node(state: AgentState) -> AgentState:
    return {
        "workflow": "Done",
        "terminal_reason": "spec verified by TLC and Python passed spec-derived tests",
        "history": state.get("history", []) + ["-> Done"],
    }


def code_fail_node(state: AgentState) -> AgentState:
    return {
        "workflow": "CodeFail",
        "terminal_reason": "spec verified by TLC, but Python did not pass spec-derived tests",
        "history": state.get("history", []) + ["-> CodeFail"],
    }


def spec_fail_node(state: AgentState) -> AgentState:
    return {
        "workflow": "SpecFail",
        "terminal_reason": _spec_error(state) or "unable to produce a TLC-valid spec",
        "history": state.get("history", []) + ["-> SpecFail"],
    }


def route_after_spec_check(state: AgentState) -> Literal["derive_tests", "repair_spec", "spec_fail"]:
    result = state.get("spec_result")
    if result and result.get("passed"):
        return "derive_tests"
    if state.get("spec_retries", 0) < state.get("max_spec_retries", 3):
        return "repair_spec"
    return "spec_fail"


def route_after_code_test(state: AgentState) -> Literal["done", "repair_code", "code_fail"]:
    result = state.get("last_result")
    if result and result.get("passed"):
        return "done"
    if state.get("code_retries", 0) < state.get("max_code_retries", 3):
        return "repair_code"
    return "code_fail"


def _spec_failure_update(state: AgentState, error: str, history: str) -> AgentState:
    result: SpecResult = {
        "passed": False,
        "module": "",
        "stdout": "",
        "stderr": "",
        "error": error,
        "states_found": None,
    }
    return {
        "spec_result": result,
        "workflow": "CheckSpec",
        "history": state.get("history", []) + [history],
    }


def _spec_result_from_tlc(tlc_result) -> SpecResult:
    return {
        "passed": tlc_result.passed,
        "module": tlc_result.module,
        "stdout": tlc_result.stdout,
        "stderr": tlc_result.stderr,
        "error": tlc_result.error,
        "states_found": tlc_result.states_found,
    }


def _spec_error(state: AgentState) -> str:
    result = state.get("spec_result") or {}
    return str(result.get("error") or result.get("stderr") or "")


def _repair_provider(state: AgentState) -> str | None:
    current = state.get("provider_used")
    if state.get("spec_retries", 0) >= 1:
        return fallback_provider(current) or current or None
    return current or None


def _code_prompt(state: AgentState, previous_code: str) -> str:
    previous = f"\nPrevious code:\n```python\n{previous_code}\n```\n" if previous_code else ""
    return (
        f"Problem:\n{state['problem']}\n\n"
        f"Required signature:\n{state['signature']}\n\n"
        f"TLC-checked TLA+ spec:\n```tla\n{state.get('tla_spec', '')}\n```\n\n"
        f"Spec-derived Python tests:\n" + "\n".join(state.get("spec_tests", [])) + "\n"
        f"{previous}\nWrite the function. Do not include tests."
    )


def _test_failure(stderr: str, failing_test: str) -> TestResult:
    return {"passed": False, "stdout": "", "stderr": stderr, "failing_test": failing_test}
