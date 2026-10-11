"""Model factory (PLAN.md §11.1): Strands' OpenAI-compatible provider pointed at Akamai hosted inference.

Two findings from the phase 1 smoke test (specs/005-agents-pipeline-api/research.md R1, R2):

- In Strands 1.59.0 the OpenAIModel config key that switches streaming is ``stream`` (default True).
  PLAN.md §11.1 calls it ``streaming``; a ``streaming=`` keyword is accepted and silently ignored.
- The Akamai gateway rejects ``"tools": []`` with HTTP 400 ("`tools` must not be an empty array").
  Strands always sends the field, so an agent with no tools (and no structured output) failed.
  ``AkamaiModel`` drops ``tools``/``tool_choice`` from the request when there are no tools.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import openai
from strands.models import Model
from strands.models.openai import OpenAIModel
from strands.types.exceptions import ModelThrottledException

from app import config

PROVIDER = "akamai"
FALLBACK_PROVIDER = "bedrock"
_local = threading.local()


class AkamaiModel(OpenAIModel):
    """OpenAIModel that omits an empty tools array, which the Akamai gateway rejects."""

    def format_request(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        request = super().format_request(*args, **kwargs)
        if not request.get("tools"):
            request.pop("tools", None)
            request.pop("tool_choice", None)
        return request


def current_provider() -> str:
    """The provider agents built on this thread should use (the runner sets it per attempt)."""
    return getattr(_local, "provider", PROVIDER)


@contextmanager
def use_provider(name: str) -> Iterator[None]:
    before = current_provider()
    _local.provider = name
    try:
        yield
    finally:
        _local.provider = before


def make_model(max_tokens: int = 1200, *, stream: bool | None = None) -> Model:
    """A fresh model client for the current provider: Akamai, or Bedrock on the runner's one retry."""
    if current_provider() == FALLBACK_PROVIDER:
        return make_fallback_model(max_tokens)
    return make_akamai_model(max_tokens, stream=stream)


def fallback_enabled() -> bool:
    return config.S.llm_fallback == FALLBACK_PROVIDER and bool(config.S.bedrock_model_id)


def is_provider_error(exc: BaseException) -> bool:
    """Worth one try on the alternate: unreachable, 5xx, or still throttled after the plugin's retries.
    A 4xx request error or invalid output is ours to fix, not the provider's (spec FR-025)."""
    if isinstance(exc, (openai.APIConnectionError, openai.InternalServerError, ModelThrottledException,
                        openai.RateLimitError)):
        return True
    return isinstance(exc, openai.APIStatusError) and exc.status_code >= 500


def make_fallback_model(max_tokens: int) -> Model:
    """BedrockModel for BEDROCK_MODEL_ID in AWS_REGION (Strands 1.59.0: model_id, region_name, max_tokens)."""
    from strands.models.bedrock import BedrockModel  # boto3 is heavy; only load it when used

    S = config.S
    return BedrockModel(model_id=S.bedrock_model_id, region_name=S.aws_region, max_tokens=max_tokens,
                        temperature=0.1)


def make_akamai_model(max_tokens: int = 1200, *, stream: bool | None = None) -> OpenAIModel:
    """A fresh Akamai client. `stream` overrides LLM_STREAMING (the smoke test compares both)."""
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
