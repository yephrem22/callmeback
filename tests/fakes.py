"""Fake Strands models for tests (research R4). No network, deterministic.

A ScriptedModel plays a list of turns. Each call to `stream()` consumes one turn and yields the
Strands stream events for it (the same shapes `OpenAIModel.format_chunk` produces):

    text_turn("hi")                      -> the model answers with text
    tool_turn("release_payment", {})     -> the model calls a tool
    structured_turn({...})               -> the model calls the structured-output tool with this input
    raise_turn(SomeError("boom"))        -> the model call raises

When the turns run out the model answers "Done." so agent loops always terminate.
`calls` records every request (messages, tool names, system prompt) for prompt assertions.
"""
from __future__ import annotations

import asyncio
import itertools
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from strands.models import Model

_ids = itertools.count(1)


@dataclass
class Turn:
    kind: str                       # text | tool | structured | raise
    text: str = ""
    name: str | None = None
    input: dict = field(default_factory=dict)
    exc: BaseException | None = None


def text_turn(text: str) -> Turn:
    return Turn("text", text=text)


def tool_turn(name: str, input: dict | None = None) -> Turn:
    return Turn("tool", name=name, input=input or {})


def structured_turn(data: dict) -> Turn:
    return Turn("structured", input=data)


def raise_turn(exc: BaseException) -> Turn:
    return Turn("raise", exc=exc)


def _usage() -> dict:
    return {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}, "metrics": {"latencyMs": 1}}}


def _text_events(text: str) -> list[dict]:
    return [{"messageStart": {"role": "assistant"}}, {"contentBlockStart": {"start": {}}},
            {"contentBlockDelta": {"delta": {"text": text}}}, {"contentBlockStop": {}},
            {"messageStop": {"stopReason": "end_turn"}}, _usage()]


def _tool_events(name: str, payload: dict) -> list[dict]:
    tid = f"tooluse_{next(_ids)}"
    return [{"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"start": {"toolUse": {"name": name, "toolUseId": tid}}}},
            {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(payload)}}}},
            {"contentBlockStop": {}}, {"messageStop": {"stopReason": "tool_use"}}, _usage()]


def _structured_tool_name(tool_specs: list[dict] | None) -> str | None:
    for spec in tool_specs or []:
        if "StructuredOutputTool" in (spec.get("description") or ""):
            return spec["name"]
    return None


class ScriptedModel(Model):
    """A Strands model that plays scripted turns. `delay` sleeps before each turn, honouring cancel."""

    def __init__(self, turns: list[Turn] | None = None, *, delay: float = 0.0):
        self.turns = list(turns or [])
        self.delay = delay
        self.calls: list[dict[str, Any]] = []
        self.config: dict[str, Any] = {"model_id": "fake-model"}
        self.cancelled = False

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs) -> AsyncIterator[dict]:
        turn = self.turns.pop(0) if self.turns else Turn("structured", input={})
        yield {"output": output_model(**turn.input)}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterator[dict]:
        self.calls.append({"messages": messages, "tools": [t["name"] for t in tool_specs or []],
                           "system_prompt": system_prompt})
        cancel = kwargs.get("cancel_signal")
        waited = 0.0
        while waited < self.delay:
            if cancel is not None and cancel.is_set():
                self.cancelled = True
                return
            await asyncio.sleep(0.02)
            waited += 0.02
        turn = self.turns.pop(0) if self.turns else text_turn("Done.")
        if turn.kind == "raise":
            raise turn.exc  # type: ignore[misc]
        if turn.kind == "text":
            events = _text_events(turn.text)
        elif turn.kind == "tool":
            events = _tool_events(turn.name or "", turn.input)
        else:
            name = _structured_tool_name(tool_specs)
            events = _tool_events(name, turn.input) if name else _text_events(json.dumps(turn.input))
        for ev in events:
            yield ev

    def prompt_text(self) -> str:
        """Everything the model was shown, flattened, for masking/wrapping assertions."""
        parts: list[str] = []
        for call in self.calls:
            parts.append(call.get("system_prompt") or "")
            for m in call["messages"]:
                for block in m.get("content", []):
                    if "text" in block:
                        parts.append(block["text"])
                    if "toolResult" in block:
                        for c in block["toolResult"].get("content", []):
                            parts.append(c.get("text") or json.dumps(c.get("json", "")))
        return "\n".join(parts)


def SlowModel(seconds: float, turns: list[Turn] | None = None) -> ScriptedModel:  # noqa: N802
    return ScriptedModel(turns, delay=seconds)


def FailingModel(exc: BaseException) -> ScriptedModel:  # noqa: N802
    return ScriptedModel([raise_turn(exc)])


@pytest.fixture
def fake_model(monkeypatch):
    """Use as: model = fake_model(ScriptedModel([...])); agents built afterwards get it."""
    from app.agents import model as model_factory

    def _install(m: ScriptedModel) -> ScriptedModel:
        monkeypatch.setattr(model_factory, "make_model", lambda *a, **k: m)
        return m

    return _install
