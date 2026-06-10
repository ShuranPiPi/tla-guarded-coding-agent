# TLA+-Guarded Self-Correcting Coding Agent

**CE 356 — Intro. to Formal Specification and Verification**
Shuran Yan, Youran Ma | Northwestern University | Spring 2026

---

## Overview

This project builds a small AI agent that solves Python programming tasks through an iterative generate-test-repair loop. The agent's control flow is formally specified in TLA+ and model-checked with TLC to guarantee workflow-level safety and liveness properties before any code runs.

The key insight: we separate the *correctness of the workflow* (which TLA+ can verify exhaustively) from the *quality of the LLM output* (which is inherently non-deterministic). The formal model treats the LLM as a non-deterministic oracle and proves that no matter what the LLM produces, the controller always behaves correctly.

## Architecture

```
┌──────────────────── LangGraph State Machine ─────────────────────┐
│                                                                   │
│   Init ──► Generate ──► Test ──┬──► Done                         │
│                 ▲              │                                  │
│                 │              ├──► Repair ──► Generate (loop)    │
│                 │              │                                  │
│                 │              └──► Fail  (retry budget spent)    │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
        │                          │
        │  LLM (gpt-4o-mini)       │  Subprocess sandbox
        │  generates / repairs     │  runs pytest assertions
        │                          │
   ┌────┴────┐               ┌─────┴─────┐
   │   RAG   │               │ Test Runner│
   │  FAISS  │               │ (timeout)  │
   └─────────┘               └───────────┘
```

### Workflow States

| State      | Description |
|------------|-------------|
| **Init**     | Accept a task (problem statement + function signature + test cases), initialize counters |
| **Generate** | Call the LLM to produce a Python function implementation |
| **Test**     | Execute the generated code against public test cases in a sandboxed subprocess |
| **Repair**   | On test failure, query RAG for similar error patterns, then call the LLM to fix the code |
| **Done**     | All public tests pass — the solution is accepted |
| **Fail**     | Retry budget exhausted — the agent gives up |

### Transition Rules

1. `Init → Generate` — always taken once at startup.
2. `Generate → Test` — after code is produced, it must be tested.
3. `Test → Done` — if all tests pass.
4. `Test → Repair` — if tests fail and `retries < MaxRetries`.
5. `Test → Fail` — if tests fail and `retries == MaxRetries`.
6. `Repair → Generate` — increment retry counter, re-generate code with error context.

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent framework | **LangGraph** + LangChain | State machine orchestration |
| LLM | OpenAI **gpt-4o-mini** | Code generation and repair |
| RAG | **FAISS** + OpenAI Embeddings | Retrieve error-fix patterns during repair |
| Test execution | Python **subprocess** | Sandboxed code runner with timeout |
| Formal verification | **TLA+** / **TLC** | Model-check the controller's state machine |

## Project Layout

```
Project/
├── agent/                    # Python agent implementation
│   ├── __init__.py
│   ├── state.py              # AgentState TypedDict (mirrors TLA+ variables)
│   ├── nodes.py              # One function per TLA+ transition
│   ├── graph.py              # LangGraph wiring of the state machine
│   ├── tools.py              # Sandboxed test runner (subprocess + timeout)
│   └── rag.py                # FAISS-based error-pattern retriever
├── tla/                      # Formal specification
│   ├── CodingAgent.tla       # TLA+ spec of the controller
│   ├── CodingAgent.cfg       # TLC configuration (constants, invariants, properties)
│   └── README.md             # Mapping between Python and TLA+ variables
├── knowledge_base/
│   └── error_patterns.json   # 12 curated Python error → cause → fix entries
├── tasks/
│   └── sample_tasks.json     # 3 sample problems (two_sum, is_palindrome, merge_intervals)
├── examples/
│   └── run_demo.py           # Run the agent on one task, print trace
├── tests/
│   └── eval.py               # Batch evaluation over all tasks
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
└── README.md                 # This file
```

## TLA+ Formal Specification

### Variable Mapping

The Python implementation and TLA+ model use a shared vocabulary so they can be compared side-by-side:

| Python (`agent.state`)         | TLA+ Variable         |
|--------------------------------|-----------------------|
| `workflow` (Init/Generate/...) | `pc` (program counter)|
| `last_result["passed"]`        | `codeOk` (BOOLEAN)    |
| *has test been run on current code?* | `tested` (BOOLEAN) |
| `retries`                      | `retries`             |
| `max_retries`                  | `MaxRetries` (constant)|

### Properties Checked

| # | Property | Type | Meaning |
|---|----------|------|---------|
| 1 | **NoAcceptBeforeValidation** | Invariant | `pc = "Done" ⇒ tested`: no solution is accepted without running tests first |
| 2 | **FailedTestGoesToRepairOrFail** | Invariant | After a failed test, the controller never skips to Done — it must go through Repair or Fail |
| 3 | **BoundedRetries** | Invariant | `retries ≤ MaxRetries`: the retry counter never exceeds the budget |
| 4 | **EventuallyTerminates** | Liveness | `◇(pc ∈ {Done, Fail})`: under weak fairness, the workflow always terminates |

### TLC Results

With `MaxRetries = 3`, TLC explores the full state space (36 distinct states) and confirms all four properties hold. The check completes in under one second.

## RAG Component

The Repair node uses Retrieval-Augmented Generation to improve repair quality. When a test fails, the traceback text is embedded and compared against a curated knowledge base of 12 common Python error patterns (e.g., `IndexError`, `KeyError`, `TypeError`, edge-case failures). The top-3 most similar patterns are injected into the repair prompt, giving the LLM concrete hints about the likely cause and fix.

The knowledge base is stored in `knowledge_base/error_patterns.json` and indexed at startup into an in-memory FAISS vector store using OpenAI's `text-embedding-3-small` model.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run a single demo
python examples/run_demo.py              # defaults to "two_sum"
python examples/run_demo.py is_palindrome

# 4. Run full evaluation
python tests/eval.py

# 5. Run TLA+ model checking
java -cp tla2tools.jar tlc2.TLC -config tla/CodingAgent.cfg tla/CodingAgent.tla
```

## Sample Tasks

The evaluation suite includes three problems of increasing complexity:

1. **two_sum** — Find two indices whose values sum to a target (hash map, O(n)).
2. **is_palindrome** — Check if a string is a palindrome ignoring non-alphanumeric characters.
3. **merge_intervals** — Merge overlapping intervals in a list.

Each task specifies public tests (used during the agent loop) and hidden tests (used only for final grading in `eval.py`).

## Design Decisions

1. **Separation of concerns**: The LangGraph graph handles control flow; nodes handle logic. This mirrors TLA+'s distinction between the transition system and its actions.
2. **Non-determinism in TLA+**: The `Generate` action uses `∃ ok ∈ BOOLEAN : codeOk' = ok` to model the LLM as a non-deterministic oracle — TLC explores both "correct" and "incorrect" code paths exhaustively.
3. **Conditional edges for routing**: The `route_after_test` function lives in the graph (not in `test_node`) so that control flow is explicit and auditable, just as it is in the TLA+ spec.
4. **Bounded retries**: Both the TLA+ spec and the Python implementation enforce a hard cap on retries, preventing infinite loops.
