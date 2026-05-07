"""LangGraph nodes — one Python function per TLA+ transition.

Each node takes the current :class:`AgentState` and returns a *partial* update
dict. LangGraph merges the update back into the state. The routing function at
the bottom, :func:`route_after_test`, is the piece that TLA+ formalises as the
``Test`` action's branching condition.
"""
from __future__ import annotations

import os
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .rag import format_for_prompt, retrieve_fixes
from .state import AgentState
from .tools import run_tests


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

def _llm() -> ChatOpenAI:
    model = os.environ.get("AGENT_MODEL", "gpt-4o-mini")
    # Low temperature — we want reproducible, focused code.
<<<<<<< HEAD
    return ChatOpenAI(model=model, temperature=0.2)
=======
    return ChatOpenAI(model = model, temperature = 0.2)
>>>>>>> 412f6f8 (20260507)


_CODE_FENCE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL)

<<<<<<< HEAD

=======
>>>>>>> 412f6f8 (20260507)
def _strip_code(text: str) -> str:
    """Extract the first ```python``` block, or return the raw text."""
    m = _CODE_FENCE.search(text)
    return (m.group(1) if m else text).strip()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def init_node(state: AgentState) -> AgentState:
    """Init: set the workflow counters. Mirrors TLA+ ``Init``."""
    return {
<<<<<<< HEAD
        "workflow": "Generate",
        "retries": 0,
        "max_retries": state.get("max_retries", int(os.environ.get("AGENT_MAX_RETRIES", "3"))),
        "history": state.get("history", []) + ["Init -> Generate"],
=======
        "workflow": "GenerateSpec",
        "retries": 0,
        "max_retries": state.get("max_retries", int(os.environ.get("AGENT_MAX_RETRIES", "3"))),
        "history": state.get("history", []) + ["Init -> GenerateSpec"],
>>>>>>> 412f6f8 (20260507)
    }


GENERATE_SYS = (
    "You are a careful Python programmer. Produce a single, self-contained "
    "implementation of the requested function. Output ONLY a ```python fenced "
    "code block — no prose, no tests, no examples."
)


def generate_node(state: AgentState) -> AgentState:
    prompt = (
        f"Problem:\n{state['problem']}\n\n"
        f"Required signature:\n{state['signature']}\n\n"
<<<<<<< HEAD
        "Write the function. Do not include tests."
    )
=======
        f"Keep in mind that these specs need to be satisfied:\n{state["tlaSpec"]}"
        "Write the function. Do not include tests."
    )
    # print(state["tlaSpec"])
>>>>>>> 412f6f8 (20260507)
    resp = _llm().invoke([SystemMessage(content=GENERATE_SYS), HumanMessage(content=prompt)])
    code = _strip_code(resp.content)
    return {
        "code": code,
        "workflow": "Test",
        "history": state.get("history", []) + ["Generate -> Test"],
    }


def test_node(state: AgentState) -> AgentState:
    """Run public tests only. Hidden tests are saved for the final grade."""
    result = run_tests(state["code"], state["public_tests"])
    return {
        "last_result": result,
        # We *don't* pick Done/Repair/Fail here — the conditional edge does,
        # so that the control-flow lives in the graph, not in the node.
        "workflow": "Test",
        "history": state.get("history", []) + [
            f"Test -> {'pass' if result['passed'] else 'fail'}"
        ],
    }


REPAIR_SYS = (
    "You are fixing a Python function that failed tests. Use the retrieved "
    "error-repair patterns as hints, but rely on the traceback to diagnose "
    "the real problem. Output ONLY the corrected function in a ```python "
    "fenced code block."
)


def repair_node(state: AgentState) -> AgentState:
    err = state["last_result"]
    query = (err.get("stderr") or "") + "\n" + (err.get("failing_test") or "")
    hits = retrieve_fixes(query, k=3)
    rag_block = format_for_prompt(hits)

    prompt = (
        f"Problem:\n{state['problem']}\n\n"
        f"Required signature:\n{state['signature']}\n\n"
        f"Previous (failing) code:\n```python\n{state['code']}\n```\n\n"
        f"Traceback / failure:\n{err.get('stderr','')}\n\n"
        f"Retrieved repair patterns:\n{rag_block}\n\n"
        "Produce a corrected implementation."
    )
    resp = _llm().invoke([SystemMessage(content=REPAIR_SYS), HumanMessage(content=prompt)])
    code = _strip_code(resp.content)
    return {
        "code": code,
        "retries": state["retries"] + 1,
        "workflow": "Generate",   # loop back to Test via Generate's edge
        "history": state.get("history", []) + [
            f"Repair #{state['retries'] + 1} -> Test  (retrieved {len(hits)} patterns)"
        ],
    }


def done_node(state: AgentState) -> AgentState:
    return {
        "workflow": "Done",
        "history": state.get("history", []) + ["-> Done"],
    }


def fail_node(state: AgentState) -> AgentState:
    return {
        "workflow": "Fail",
        "history": state.get("history", []) + ["-> Fail (retry budget exhausted)"],
    }

<<<<<<< HEAD

=======
>>>>>>> 412f6f8 (20260507)
# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def route_after_test(state: AgentState) -> Literal["done", "repair", "fail"]:
    """The only branching point in the graph — matches TLA+ Test action."""
    if state["last_result"] and state["last_result"]["passed"]:
        return "done"
    if state["retries"] < state["max_retries"]:
        return "repair"
    return "fail"
<<<<<<< HEAD
=======

# ---------------------------------------------------------------------------
# Possible extensions
# ---------------------------------------------------------------------------

SPEC_SYS = (
    "You are a careful programmer. Before producing a single, self-contained "
    "implementation of the requested function, try to specify the program first"
    "(properties, behaviours, invariants, etc.)"
    "Output ONLY a block with TLA+ specifications"
    "— no prose, no tests, no examples."
)

def generate_spec_node(state: AgentState) -> AgentState:
    prompt = (
        f"Problem:\n{state['problem']}\n\n"
        f"Required signature:\n{state['signature']}\n\n"
        "Before generating the code, try to specify(in terms of TLA+) the program"
    )
    resp = _llm().invoke([SystemMessage(content = SPEC_SYS), 
                          HumanMessage(content = prompt)])
    spec = resp.content
    return {
        "tlaSpec": spec,
        "workflow": "Test",
        "history": state.get("history", []) + ["GenerateSpec -> Generate"],
    }
>>>>>>> 412f6f8 (20260507)
