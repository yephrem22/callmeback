"""Time-boxed agent runner (PLAN.md §11.2; contracts/agents.md; analyze C2).

    result, outcome = run_agent("analyst", invoice_id, fn, timeout_s, fallback)

`fn(ctx)` runs on the AGENTS pool. On timeout the run's cancel event is set: agents pass it to
Strands as `cancel_signal=` and closure-bound tools refuse to act once it is set, so a late run
stops and frees its thread instead of acting after the fallback. On timeout, exception or
invalid structured output we write a `fallback` trace row, mark the invoice `ai_fallback`,
audit `ai_fallback`, and return `fallback()`. A late result is discarded.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar

from strands.types.exceptions import StructuredOutputException

from app import audit, db, executors, traces
from app.agents import model as model_factory
from app.ai_mode import effective_ai_mode

log = logging.getLogger("agents.runner")
T = TypeVar("T")
Outcome = Literal["result", "fallback"]


@dataclass
class RunContext:
    run_id: str
    agent: str
    subject_id: str
    cancel: threading.Event = field(default_factory=threading.Event)

    def check(self) -> None:
        """Tools call this before acting; raises once the run has been cancelled."""
        if self.cancel.is_set():
            raise RuntimeError("run cancelled after its timeout; not acting")


def _actor(agent_name: str) -> str:
    return "agent:" + agent_name.split(":", 1)[0]


def _record_fallback(ctx: RunContext, reason: str) -> None:
    try:
        traces.write(ctx.subject_id, run_id=ctx.run_id, agent=ctx.agent, kind="fallback", summary=reason)
        if reason == "AI off":
            return
        c = db.connect()
        try:
            if ctx.subject_id.startswith("inv_"):
                c.execute("UPDATE invoices SET ai_fallback=1 WHERE id=?", (ctx.subject_id,))
            audit.append(ctx.subject_id, _actor(ctx.agent), "ai_fallback",
                         {"agent": ctx.agent, "run_id": ctx.run_id, "reason": reason}, conn=c)
        finally:
            c.close()
    except Exception:  # noqa: BLE001 - recording a fallback must never break the fallback itself
        log.exception("could not record fallback for %s", ctx.run_id)


def run_agent(agent_name: str, subject_id: str, fn: Callable[[RunContext], T], timeout_s: float,
              fallback: Callable[[], T]) -> tuple[T, Outcome]:
    if executors.on_agents_thread():
        raise RuntimeError("run_agent called on an AGENTS thread (deadlock rule, PLAN.md §6)")
    ctx = RunContext(traces.new_run_id(), agent_name, subject_id)
    if effective_ai_mode() != "live":
        _record_fallback(ctx, "AI off")
        return fallback(), "fallback"
    t0 = time.monotonic()
    ok, value, exc = _attempt(fn, ctx, model_factory.PROVIDER, timeout_s)
    if ok:
        return value, "result"
    remaining = timeout_s - (time.monotonic() - t0)
    if exc is not None and model_factory.fallback_enabled() and model_factory.is_provider_error(exc) and remaining > 0.5:
        # P3 (FR-025): one retry on the alternate provider, inside the same time budget
        traces.write(subject_id, run_id=ctx.run_id, agent=agent_name, kind="error", name=model_factory.PROVIDER,
                     summary=f"{value}; retrying once on {model_factory.FALLBACK_PROVIDER}")
        ctx = RunContext(ctx.run_id, agent_name, subject_id)
        ok, value, exc = _attempt(fn, ctx, model_factory.FALLBACK_PROVIDER, remaining)
        if ok:
            return value, "result"
    _record_fallback(ctx, value)
    return fallback(), "fallback"


def _attempt(fn: Callable[[RunContext], T], ctx: RunContext, provider: str,
             timeout_s: float) -> tuple[bool, Any, BaseException | None]:
    """One run on `provider`. Returns (True, result, None) or (False, reason, exception or None)."""

    def call() -> T:
        with model_factory.use_provider(provider):
            return fn(ctx)

    future: Future = executors.AGENTS.submit(call)
    try:
        return True, future.result(timeout=timeout_s), None
    except FuturesTimeout:
        ctx.cancel.set()
        return False, f"timed out after {timeout_s:g} s", None
    except StructuredOutputException as e:
        return False, f"StructuredOutputException: {e}", e
    except Exception as e:  # noqa: BLE001 - any agent failure falls back to rules
        return False, f"{type(e).__name__}: {e}", e


def start_agent(agent_name: str, subject_id: str, fn: Callable[[RunContext], T], timeout_s: float,
                fallback: Callable[[], T], on_done: Callable[[T, Outcome], Any]) -> Future:
    """Run an agent without blocking the caller: a JOBS task that waits on AGENTS, then calls on_done."""

    def job() -> None:
        result, outcome = run_agent(agent_name, subject_id, fn, timeout_s, fallback)
        try:
            on_done(result, outcome)
        except Exception:  # noqa: BLE001
            log.exception("on_done failed for %s on %s", agent_name, subject_id)

    return executors.JOBS.submit(job)
