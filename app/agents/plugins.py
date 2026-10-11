"""Strands plugins (PLAN.md §11.3; contracts/agents.md).

Strands 1.59.0 notes (research R1, R5; analyze C1):
- every Plugin calls super().__init__(): that is where @hook methods are discovered;
- `agent_kwargs()` disables Strands' built-in ModelRetryStrategy (6 attempts, 4 s → 240 s backoff)
  so RateLimitPlugin is the only retry policy.

No `from __future__ import annotations` here: @hook infers event types from the annotations.
"""
import threading
import time
from typing import Any

from strands.hooks import (AfterInvocationEvent, AfterModelCallEvent, AfterToolCallEvent, BeforeInvocationEvent,
                           BeforeModelCallEvent, BeforeToolCallEvent)
from strands.plugins import Plugin, hook
from strands.tools.executors import SequentialToolExecutor
from strands.types.exceptions import ModelThrottledException

from app import audit, config, ledger, traces
from app.agents.model import PROVIDER

MAX_RETRIES = 3
DEFAULT_RESET_S = 5.0
_sleep = time.sleep  # patched in tests


def agent_kwargs() -> dict[str, Any]:
    """Constructor arguments every agent shares (PLAN.md §11.2)."""
    return {"tool_executor": SequentialToolExecutor(), "callback_handler": None, "retry_strategy": None}


# ---- payment guard -----------------------------------------------------------------

class PaymentGuardPlugin(Plugin):
    """Cancels `release_payment` unless ledger.can_release passes. The headline Strands feature."""

    name = "payment-guard"

    def __init__(self, invoice_id: str, run_id: str = "", agent: str = "payments"):
        super().__init__()
        self.invoice_id = invoice_id
        self.run_id = run_id or traces.new_run_id()
        self.agent = agent

    @hook
    def guard(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != "release_payment":
            return
        ok, reason = ledger.can_release(self.invoice_id)
        if ok:
            traces.write(self.invoice_id, run_id=self.run_id, agent=self.agent, kind="guard_allow",
                         name="release_payment", summary=reason)
            audit.append(self.invoice_id, "plugin:payment-guard", "guard_allowed", {"reason": reason, "run_id": self.run_id})
        else:
            event.cancel_tool = f"BLOCKED by payment policy: {reason}"
            traces.write(self.invoice_id, run_id=self.run_id, agent=self.agent, kind="guard_block",
                         name="release_payment", summary=f"BLOCKED: {reason}")
            audit.append(self.invoice_id, "plugin:payment-guard", "guard_blocked", {"reason": reason, "run_id": self.run_id})


# ---- trace --------------------------------------------------------------------------

def _summarise_input(tool_input: Any) -> str:
    if isinstance(tool_input, dict) and tool_input:
        return ", ".join(f"{k}={v}" for k, v in tool_input.items())
    return "no input"


class TracePlugin(Plugin):
    """Writes run_start, model_call, tool_call and run_end rows for one run."""

    name = "trace"

    def __init__(self, subject_id: str, agent: str, run_id: str, provider: str = PROVIDER):
        super().__init__()
        self.subject_id, self.agent, self.run_id, self.provider = subject_id, agent, run_id, provider
        self._run_t0: float | None = None
        self._model_t0: float | None = None
        self._tool_t0: dict[str, float] = {}

    def _write(self, kind: str, **kw: Any) -> None:
        traces.write(self.subject_id, run_id=self.run_id, agent=self.agent, kind=kind, **kw)

    @hook
    def on_start(self, event: BeforeInvocationEvent) -> None:
        self._run_t0 = time.perf_counter()
        self._write("run_start", summary=f"{self.agent} agent started")

    @hook
    def on_model_start(self, event: BeforeModelCallEvent) -> None:
        self._model_t0 = time.perf_counter()

    @hook
    def on_model_end(self, event: AfterModelCallEvent) -> None:
        ms = int((time.perf_counter() - (self._model_t0 or time.perf_counter())) * 1000)
        if event.exception is not None:
            self._write("model_call", name=self.provider, duration_ms=ms,
                        summary=f"error: {type(event.exception).__name__}: {event.exception}")
        else:
            self._write("model_call", name=self.provider, duration_ms=ms, summary="ok")

    @hook
    def on_tool_start(self, event: BeforeToolCallEvent) -> None:
        self._tool_t0[event.tool_use.get("toolUseId", "")] = time.perf_counter()

    @hook
    def on_tool_end(self, event: AfterToolCallEvent) -> None:
        tid = event.tool_use.get("toolUseId", "")
        ms = int((time.perf_counter() - self._tool_t0.pop(tid, time.perf_counter())) * 1000)
        status = (event.result or {}).get("status", "error") if event.exception is None else "error"
        if event.cancel_message:
            status = "cancelled"
        self._write("tool_call", name=event.tool_use.get("name"), duration_ms=ms,
                    summary=f"{status}: {_summarise_input(event.tool_use.get('input'))}")
        if event.exception is not None:
            self._write("error", name=event.tool_use.get("name"), summary=f"{type(event.exception).__name__}: {event.exception}")

    @hook
    def on_end(self, event: AfterInvocationEvent) -> None:
        ms = int((time.perf_counter() - (self._run_t0 or time.perf_counter())) * 1000)
        tokens = None
        try:
            usage = getattr(getattr(event.result, "metrics", None), "accumulated_usage", None) or {}
            tokens = usage.get("totalTokens")
        except Exception:  # noqa: BLE001 - metrics are best effort
            tokens = None
        self._write("run_end", duration_ms=ms, summary=f"done; tokens {tokens}" if tokens else "done")


# ---- rate limit -----------------------------------------------------------------------

class _Bucket:
    """Process-wide token bucket: `rpm` model calls per 60 s, shared by every agent."""

    def __init__(self, rpm: int):
        self.capacity = max(1, rpm)
        self.tokens = float(self.capacity)
        self.rate = self.capacity / 60.0
        self.t = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.rate
            _sleep(min(wait, 2.0))


_bucket = _Bucket(config.S.llm_rpm)


def reset_bucket() -> None:
    global _bucket
    _bucket = _Bucket(config.S.llm_rpm)


def _is_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, ModelThrottledException):
        return True
    text = f"{exc} {exc.__cause__ or ''}".lower()
    return "429" in text or "rate limit" in text


def _reset_seconds(exc: BaseException) -> float:
    for e in (exc, exc.__cause__):
        headers = getattr(getattr(e, "response", None), "headers", None)
        if headers:
            value = headers.get("x-ratelimit-reset")
            if value is not None:
                try:
                    return max(0.0, min(float(value), 30.0))
                except (TypeError, ValueError):
                    pass
    return DEFAULT_RESET_S


class RateLimitPlugin(Plugin):
    """Meters model calls and retries rate-limited ones at most 3 times per invocation."""

    name = "rate-limit"

    def __init__(self) -> None:
        super().__init__()

    @hook
    def before_model(self, event: BeforeModelCallEvent) -> None:
        _bucket.take()

    @hook
    def after_model(self, event: AfterModelCallEvent) -> None:
        exc = event.exception
        if exc is None or not _is_rate_limit(exc):
            return
        state = event.invocation_state
        n = state.get("_cmb_rate_retries", 0)
        if n >= MAX_RETRIES:
            return
        state["_cmb_rate_retries"] = n + 1
        _sleep(_reset_seconds(exc))
        event.retry = True
