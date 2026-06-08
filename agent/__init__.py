"""TLA+-guarded self-correcting coding agent."""
from __future__ import annotations

__all__ = ["build_agent", "run_agent", "AgentState", "LLMClient", "LLMUnavailableError"]


def __getattr__(name: str):
    if name in {"build_agent", "run_agent"}:
        from .graph import build_agent, run_agent

        return {"build_agent": build_agent, "run_agent": run_agent}[name]
    if name == "AgentState":
        from .state import AgentState

        return AgentState
    if name in {"LLMClient", "LLMUnavailableError"}:
        from .llm import LLMClient, LLMUnavailableError

        return {"LLMClient": LLMClient, "LLMUnavailableError": LLMUnavailableError}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
