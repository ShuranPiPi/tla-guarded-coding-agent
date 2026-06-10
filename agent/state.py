"""Agent state shared by the Python workflow and the TLA+ controller model."""
from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

SpecMode = Literal["example", "specification"]

Workflow = Literal[
    "Init",
    "GenerateSpec",
    "CheckSpec",
    "RepairSpec",
    "DeriveTests",
    "GenerateCode",
    "TestCode",
    "RepairCode",
    "Done",
    "CodeFail",
    "SpecFail",
]


class TestResult(TypedDict):
    """Outcome of running generated code against tests."""

    passed: bool
    stdout: str
    stderr: str
    failing_test: Optional[str]


class SpecResult(TypedDict):
    """Outcome of parsing and checking a generated spec bundle."""

    passed: bool
    module: str
    stdout: str
    stderr: str
    error: str
    states_found: Optional[int]


class AgentState(TypedDict, total=False):
    # --- task description (immutable after Init) -------------------------
    problem: str
    signature: str
    public_tests: List[str]
    hidden_tests: List[str]

    # --- spec generation / checking -------------------------------------
    workflow: Workflow
    spec_mode: SpecMode
    spec_bundle_raw: str
    structured_spec: str
    tla_spec: str
    tla_cfg: str
    spec_tests: List[str]
    spec_result: Optional[SpecResult]
    spec_retries: int
    max_spec_retries: int

    # --- code generation / checking -------------------------------------
    code: str
    last_result: Optional[TestResult]
    code_retries: int
    max_code_retries: int

    # --- provider and auditing ------------------------------------------
    provider_used: str
    terminal_reason: str
    history: List[str]
