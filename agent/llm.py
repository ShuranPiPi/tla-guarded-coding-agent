"""LLM provider abstraction for OpenAI and Gemini.

The agent prefers OpenAI when both providers are configured, but it can run
with Gemini only. Real API keys must come from environment variables.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Literal

ProviderName = Literal["openai", "gemini"]


class LLMUnavailableError(RuntimeError):
    """Raised when no configured provider can satisfy a request."""


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: ProviderName
    model: str


def _has_env(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def available_providers() -> list[ProviderName]:
    providers: list[ProviderName] = []
    if _has_env("OPENAI_API_KEY"):
        providers.append("openai")
    if _has_env("GEMINI_API_KEY"):
        providers.append("gemini")
    return providers


def select_provider(preferred: str | None = None, exclude: Iterable[str] = ()) -> ProviderName:
    """Pick a provider using env configuration.

    `preferred` may be "auto", "openai", or "gemini". In auto mode OpenAI is
    preferred when available; Gemini is the fallback.
    """
    excluded = set(exclude)
    requested = (preferred or os.environ.get("AGENT_PROVIDER", "auto")).strip().lower()
    configured = [p for p in available_providers() if p not in excluded]

    if requested == "auto":
        if configured:
            return configured[0]
        raise LLMUnavailableError(
            "No LLM provider is configured. Set OPENAI_API_KEY or GEMINI_API_KEY."
        )

    if requested not in {"openai", "gemini"}:
        raise LLMUnavailableError(
            f"Unsupported AGENT_PROVIDER={requested!r}; use auto, openai, or gemini."
        )

    provider = requested  # type: ignore[assignment]
    if provider in configured:
        return provider
    env_name = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
    raise LLMUnavailableError(f"Provider {provider!r} requires {env_name}.")


def fallback_provider(current: str | None) -> ProviderName | None:
    """Return a different configured provider, if one exists."""
    configured = available_providers()
    for provider in configured:
        if provider != current:
            return provider
    return None


class LLMClient:
    """Small adapter exposing a provider-neutral `generate` method."""

    def __init__(
        self,
        provider: str | None = None,
        openai_model: str | None = None,
        gemini_model: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        self.provider = select_provider(provider)
        self.openai_model = openai_model or os.environ.get("AGENT_MODEL", "gpt-4o-mini")
        self.gemini_model = gemini_model or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        self.temperature = temperature

    @property
    def model(self) -> str:
        return self.openai_model if self.provider == "openai" else self.gemini_model

    def generate(self, system: str, prompt: str) -> LLMResponse:
        if self.provider == "openai":
            return self._generate_openai(system, prompt)
        return self._generate_gemini(system, prompt)

    def _generate_openai(self, system: str, prompt: str) -> LLMResponse:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LLMUnavailableError(
                "OpenAI provider requires langchain-core and langchain-openai."
            ) from exc

        try:
            llm = ChatOpenAI(model=self.openai_model, temperature=self.temperature)
            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        except Exception as exc:
            raise LLMUnavailableError(f"OpenAI generation failed: {exc}") from exc
        return LLMResponse(text=str(resp.content), provider="openai", model=self.openai_model)

    def _generate_gemini(self, system: str, prompt: str) -> LLMResponse:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LLMUnavailableError(
                "Gemini provider requires the google-genai package."
            ) from exc

        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
        )
        try:
            resp = client.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise LLMUnavailableError(f"Gemini generation failed: {exc}") from exc
        return LLMResponse(text=resp.text or "", provider="gemini", model=self.gemini_model)
