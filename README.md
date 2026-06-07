# TLA+/PlusCal-Guarded Self-Correcting Coding Agent

**CE 356 — Intro to Formal Specification and Verification** Shuran Yan, Youran Ma, Zhuoer Zhang | Northwestern University | Spring 2026  

---

## Overview

This project builds an advanced AI agent that solves complex programming tasks through a **Two-Stage Agentic Workflow**. Instead of generating Python code blindly and relying solely on unit tests, our agent first attempts to mathematically specify and verify the algorithm using **PlusCal and TLA+ (TLC Model Checker)**. 

The key insight: By forcing the LLM to draft and verify the algorithmic logic as a formal PlusCal blueprint first, we significantly reduce deep logical flaws (such as sign flips in linear programming constraint matrices). We effectively separate the *correctness of the abstract workflow* from the *syntactic generation of the final Python code*.

## Architecture

Our LangGraph state machine operates in two distinct phases:

### Phase 1: Formal Specification & Verification (PlusCal)
The agent breaks down the problem, writes PlusCal specifications for each subtask, and rigorously checks them using TLC.

```text
┌───────────────────────── LangGraph: Phase 1 ─────────────────────────┐
│                                                                      │
│  Init ──► Plan ──► Split ──► Prove ──► Check ──┬──► (Next Subtask)   │
│                                ▲               │                     │
│                                ├─── Repair ◄───┤ (TLC Errors)        │
│                                │               │                     │
│                                └─── Skip ◄─────┘ (Retry exhausted)   │
└──────────────────────────────────────────────────────────────────────┘