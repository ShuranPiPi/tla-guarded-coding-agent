"""Wire the nodes into the formal-spec-guarded LangGraph state machine."""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    check_spec_node,
    code_fail_node,
    derive_tests_node,
    done_node,
    generate_code_node,
    generate_spec_node,
    init_node,
    repair_code_node,
    repair_spec_node,
    route_after_code_test,
    route_after_spec_check,
    spec_fail_node,
    test_code_node,
)
from .state import AgentState


def build_agent():
    g = StateGraph(AgentState)

    g.add_node("init", init_node)
    g.add_node("generate_spec", generate_spec_node)
    g.add_node("check_spec", check_spec_node)
    g.add_node("repair_spec", repair_spec_node)
    g.add_node("derive_tests", derive_tests_node)
    g.add_node("generate_code", generate_code_node)
    g.add_node("test_code", test_code_node)
    g.add_node("repair_code", repair_code_node)
    g.add_node("done", done_node)
    g.add_node("code_fail", code_fail_node)
    g.add_node("spec_fail", spec_fail_node)

    g.set_entry_point("init")
    g.add_edge("init", "generate_spec")
    g.add_edge("generate_spec", "check_spec")
    g.add_conditional_edges(
        "check_spec",
        route_after_spec_check,
        {
            "derive_tests": "derive_tests",
            "repair_spec": "repair_spec",
            "spec_fail": "spec_fail",
        },
    )
    g.add_edge("repair_spec", "check_spec")
    g.add_edge("derive_tests", "generate_code")
    g.add_edge("generate_code", "test_code")
    g.add_conditional_edges(
        "test_code",
        route_after_code_test,
        {
            "done": "done",
            "repair_code": "repair_code",
            "code_fail": "code_fail",
        },
    )
    g.add_edge("repair_code", "test_code")
    g.add_edge("done", END)
    g.add_edge("code_fail", END)
    g.add_edge("spec_fail", END)

    return g.compile()


def run_agent(
    task: dict,
    max_retries: int | None = None,
    max_spec_retries: int | None = None,
    max_code_retries: int | None = None,
    spec_mode: str | None = None,
) -> AgentState:
    """Run the full spec-guarded workflow for one task."""
    app = build_agent()
    spec_budget = max_spec_retries if max_spec_retries is not None else (max_retries or 3)
    code_budget = max_code_retries if max_code_retries is not None else (max_retries or 3)
    initial: AgentState = {
        "problem": task["problem"],
        "signature": task["signature"],
        "public_tests": task.get("public_tests", []),
        "hidden_tests": task.get("hidden_tests", []),
        "workflow": "Init",
        "spec_mode": spec_mode or "",
        "spec_bundle_raw": "",
        "structured_spec": "",
        "tla_spec": "",
        "tla_cfg": "",
        "spec_tests": [],
        "spec_result": None,
        "spec_retries": 0,
        "max_spec_retries": spec_budget,
        "code": "",
        "last_result": None,
        "code_retries": 0,
        "max_code_retries": code_budget,
        "provider_used": "",
        "terminal_reason": "",
        "history": [],
    }
    return app.invoke(initial, config={"recursion_limit": 100})
