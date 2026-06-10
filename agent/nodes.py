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
    "You write small, finite TLA+ modules that TLC can model-check. "
    "Use the finite-state template in the user prompt almost verbatim. "
    "Do not use PlusCal, TLAPS, Reals, Nat, SUBSET, CHOOSE, recursion, or unbounded sets. "
    "Output fenced ```tla``` and ```json``` blocks. A ```cfg``` block is optional because "
    "the controller will synthesize cfg from the TLA definitions."
)

FINITE_TLA_EXAMPLE = """\
```tla
---- MODULE TwoSumFiniteSpec ----
EXTENDS Naturals, Integers, Sequences, TLC

VARIABLE pc

Examples == {
    [nums |-> <<2, 7, 11, 15>>, target |-> 9, out |-> <<1, 2>>],
    [nums |-> <<3, 2, 4>>, target |-> 6, out |-> <<2, 3>>]
}

ValidExample(e) ==
    /\ e.out[1] < e.out[2]
    /\ e.out[1] \\in 1..Len(e.nums)
    /\ e.out[2] \\in 1..Len(e.nums)
    /\ e.nums[e.out[1]] + e.nums[e.out[2]] = e.target

Init == pc = "check"

Next == pc' = "done"

Spec == Init /\\ [][Next]_pc

TypeOK == pc \\in {"check", "done"}

Correct == \\A e \\in Examples : ValidExample(e)
====
```
```json
{"spec_tests": [
  "assert two_sum([2, 7, 11, 15], 9) == (0, 1)",
  "assert two_sum([3, 2, 4], 6) == (1, 2)"
]}
```
"""

SPEC_PROMPT_TEMPLATE = """\
Problem:
{problem}

Required Python signature:
{signature}

Public tests for context only:
{public_tests}

Goal:
Generate a finite example-based TLA+ module that TLC can check. The TLA+ does
not need to prove the algorithm for all possible inputs. It should formalize a
small finite set of examples and a Correct invariant over those examples.

Hard rules:
- Use only finite literal sets/sequences.
- Use 1-based TLA+ sequence indexes, even when Python tests use 0-based indexes.
- Define these operators exactly: Init, Next, Spec, TypeOK, Correct.
- Use a single variable named pc with states "check" and "done".
- End the module with ====.
- Output a JSON block with spec_tests copied or derived from the finite examples.
- Do not output prose outside fenced blocks.

Follow this working template closely, changing only module name, Examples,
ValidExample, and spec_tests:
{finite_example}
"""

SPEC_REPAIR_SYS = (
    "You repair TLA+ specs so TLC can check them. Preserve the task intent, "
    "but prioritize producing a syntactically valid, finite, TLC-checkable module. "
    "Use the finite-state template from the prompt; do not invent a new style."
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
    prompt = _spec_prompt(state)
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
        f"Likely fix:\n{_repair_advice(_spec_error(state))}\n\n"
        "Rewrite the bundle using this known-good finite template style:\n"
        f"{FINITE_TLA_EXAMPLE}\n"
        "Return corrected ```tla``` and ```json``` blocks. No prose."
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


def _spec_prompt(state: AgentState) -> str:
    return SPEC_PROMPT_TEMPLATE.format(
        problem=state["problem"],
        signature=state["signature"],
        public_tests="\n".join(state.get("public_tests", [])) or "(none)",
        finite_example=FINITE_TLA_EXAMPLE,
    )


def _repair_advice(error: str) -> str:
    lowered = error.lower()
    if "attempted to enumerate" in lowered or "not enumerable" in lowered:
        return "Replace every unbounded set with a finite literal set or sequence."
    if "unknown operator" in lowered or "undefined" in lowered:
        return "Define every helper operator you use, or remove it and inline the expression."
    if "semantic" in lowered or "parse" in lowered or "syntax" in lowered:
        return "Copy the finite template exactly and only edit Examples, ValidExample, and spec_tests."
    if "deadlock" in lowered:
        return "Set CHECK_DEADLOCK FALSE and keep Next as a simple transition from \"check\" to \"done\"."
    if "unexpected exception" in lowered:
        return "Avoid complex records, CHOOSE, CASE, recursive operators, and module instantiation."
    return "Use the finite template exactly; keep the model small and all sets enumerable."
