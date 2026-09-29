"""Shared text generation for the configured AI provider."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

Task = Literal["primary", "fast"]


def get_provider() -> str:
    # Existing deployments keep Claude until explicitly switched.
    provider = os.getenv("LLM_PROVIDER", "claude").strip().lower()
    if provider not in {"openai", "claude"}:
        raise ValueError("LLM_PROVIDER must be openai or claude")
    return provider


def is_api_key_configured() -> bool:
    variable = "OPENAI_API_KEY" if get_provider() == "openai" else "CLAUDE_API_KEY"
    return bool(os.getenv(variable, "").strip())


def get_model(task: Task = "primary") -> str:
    if get_provider() == "openai":
        variable, default = (
            ("OPENAI_FAST_MODEL", "gpt-4.1-mini") if task == "fast"
            else ("OPENAI_MODEL", "gpt-6-astra")
        )
    else:
        variable, default = (
            ("CLAUDE_FAST_MODEL", "claude-haiku-4-5-20251001") if task == "fast"
            else ("CLAUDE_MODEL", "claude-sonnet-4-6")
        )
    return os.getenv(variable, "").strip() or default


@lru_cache(maxsize=1)
def _openai_client():
    from openai import AsyncOpenAI
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return AsyncOpenAI(api_key=key, base_url="https://api.openai.com/v1", timeout=60, max_retries=0)


@lru_cache(maxsize=1)
def _claude_client():
    from anthropic import AsyncAnthropic
    key = os.getenv("CLAUDE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("CLAUDE_API_KEY is not configured")
    return AsyncAnthropic(api_key=key, timeout=60, max_retries=0)


async def generate_text(
    messages: list[dict], *, system: str = "", max_tokens: int = 1024,
    temperature: float | None = None, task: Task = "primary",
) -> str:
    model = get_model(task)
    if get_provider() == "openai":
        params = {"model": model, "input": messages, "max_output_tokens": max_tokens, "store": False}
        if system:
            params["instructions"] = system
        if model.startswith(("gpt-6", "gpt-5", "o1", "o3", "o4")):
            # Reasoning consumes the output budget too. Do not send temperature
            # for reasoning models; GPT-6 Astra requires at least low effort.
            params["reasoning"] = {"effort": os.getenv("OPENAI_REASONING_EFFORT", "low")}
            params["max_output_tokens"] = max_tokens + 2048
        elif temperature is not None:
            params["temperature"] = temperature
        response = await _openai_client().responses.create(**params)
        if response.status != "completed":
            raise RuntimeError("AI response was not completed")
        result = response.output_text.strip()
    else:
        params = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if system:
            params["system"] = system
        if temperature is not None:
            params["temperature"] = temperature
        response = await _claude_client().messages.create(**params)
        result = "\n".join(block.text for block in response.content if block.type == "text").strip()
    if not result:
        raise RuntimeError("AI returned an empty response")
    return result
