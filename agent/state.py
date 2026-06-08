"""Agent state — kept in lock-step with the TLA+ specification.

Every field here appears as a variable in ``tla/CodingAgent.tla`` so that the
Python implementation and the formal model can be compared side by side.
"""
from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

# The six workflow states from the proposal. These are the exact values
# of the ``pc`` (program counter) variable in the TLA+ spec.
Workflow = Literal["Init", "Generate", "Test", "Repair", "Done", "Fail"]


class TestResult(TypedDict):
    """Outcome of running the generated code against the task's tests."""

    passed: bool
    stdout: str
    stderr: str
    failing_test: Optional[str]


class AgentState(TypedDict, total=False):
    # --- task description (immutable after Init) -------------------------
    problem: str            # natural-language problem statement
    signature: str          # required function signature, e.g. "def foo(x):"
    public_tests: List[str] # python `assert` statements
    hidden_tests: List[str] # extra tests only used to grade final solution

    # --- mutable during the run ----------------------------------------
    workflow: Workflow      # current control-flow state  (TLA+: pc)
    code: str               # latest generated solution    (TLA+: code)
    last_result: Optional[TestResult]   # last Test outcome (TLA+: tested)
    retries: int            # number of repair attempts so far (TLA+: retries)
    max_retries: int        # upper bound on retries           (TLA+: MaxRetries)

    # --- auditing ------------------------------------------------------
    history: List[str]      # human-readable trace for the report
