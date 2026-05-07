"""Wire the nodes into a LangGraph state machine.

The graph below is a one-for-one Python rendering of the automaton in
``tla/CodingAgent.tla``:

    Init ──► Generate ──► Test ──► [passed?] ─► Done
                 ▲                      │
                 │                      ├─► [retries<Max] ─► Repair ─► Generate
                 │                      └─► Fail
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from .nodes import (
    done_node,
    fail_node,
    generate_node,
    init_node,
    repair_node,
    route_after_test,
    test_node,
<<<<<<< HEAD
=======
    generate_spec_node,
>>>>>>> 412f6f8 (20260507)
)
from .state import AgentState


def build_agent():
    g = StateGraph(AgentState)

    g.add_node("init", init_node)
<<<<<<< HEAD
=======
    g.add_node("generate_spec", generate_spec_node)
>>>>>>> 412f6f8 (20260507)
    g.add_node("generate", generate_node)
    g.add_node("test", test_node)
    g.add_node("repair", repair_node)
    g.add_node("done", done_node)
    g.add_node("fail", fail_node)

    g.set_entry_point("init")
<<<<<<< HEAD
    g.add_edge("init", "generate")
=======
    g.add_edge("init", "generate_spec")
    g.add_edge("generate_spec", "generate")
>>>>>>> 412f6f8 (20260507)
    g.add_edge("generate", "test")
    g.add_conditional_edges(
        "test",
        route_after_test,
        {"done": "done", "repair": "repair", "fail": "fail"},
    )
    g.add_edge("repair", "generate")  # loop
    g.add_edge("done", END)
    g.add_edge("fail", END)

    return g.compile()


def run_agent(task: dict, max_retries: int = 3) -> AgentState:
    """Convenience wrapper. `task` is a dict with problem/signature/tests."""
    app = build_agent()
    initial: AgentState = {
        "problem": task["problem"],
        "signature": task["signature"],
        "public_tests": task["public_tests"],
        "hidden_tests": task.get("hidden_tests", []),
        "workflow": "Init",
        "code": "",
<<<<<<< HEAD
=======
        "tlaSpec": "",
>>>>>>> 412f6f8 (20260507)
        "last_result": None,
        "retries": 0,
        "max_retries": max_retries,
        "history": [],
    }
    # recursion_limit guards against accidental unbounded loops. With
    # max_retries=3 we execute at most ~14 nodes.
    return app.invoke(initial, config={"recursion_limit": 50})
