"""Model factory (PLAN.md §11.1): Strands' OpenAI-compatible provider pointed at Akamai hosted inference.

Two findings from the phase 1 smoke test (specs/005-agents-pipeline-api/research.md R1, R2):

- In Strands 1.59.0 the OpenAIModel config key that switches streaming is ``stream`` (default True).
  PLAN.md §11.1 calls it ``streaming``; a ``streaming=`` keyword is accepted and silently ignored.
- The Akamai gateway rejects ``"tools": []`` with HTTP 400 ("`tools` must not be an empty array").
  Strands always sends the field, so an agent with no tools (and no structured output) failed.
  ``AkamaiModel`` drops ``tools``/``tool_choice`` from the request when there are no tools.
"""
from __future__ import annotations

from typing import Any

from strands.models.openai import OpenAIModel

from app import config

PROVIDER = "akamai"


class AkamaiModel(OpenAIModel):
    """OpenAIModel that omits an empty tools array, which the Akamai gateway rejects."""

    def format_request(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        request = super().format_request(*args, **kwargs)
        if not request.get("tools"):
            request.pop("tools", None)
            request.pop("tool_choice", None)
        return request


def make_model(max_tokens: int = 1200, *, stream: bool | None = None) -> OpenAIModel:
    """A fresh model client. `stream` overrides LLM_STREAMING (the smoke test compares both)."""
    S = config.S
    return AkamaiModel(
        client_args={"api_key": S.akamai_api_key, "base_url": S.akamai_base_url,
                     "timeout": 30.0, "max_retries": 1},
        model_id=S.model_id,
        params={"max_tokens": max_tokens, "temperature": 0.1},
        stream=S.llm_streaming if stream is None else stream,
    )


def model_settings() -> dict[str, Any]:
    """Non-secret settings, safe for traces, health and the smoke report."""
    S = config.S
    return {"provider": PROVIDER, "base_url": S.akamai_base_url, "model_id": S.model_id,
            "stream": S.llm_streaming, "rpm": S.llm_rpm}
