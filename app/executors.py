"""The only two thread pools in the app (PLAN.md §6; research R5; analyze A1).

JOBS runs orchestration (pipeline steps, agent waiters, the verifier poller).
AGENTS runs Strands agent invocations only.
Deadlock rule: a JOBS task may wait on an AGENTS future, never the reverse, and no task waits
on a future from its own pool. `runner.run_agent` enforces it with `on_agents_thread()`.

The pools are switchable so tests can run everything inline (deterministic) and modules can
import `JOBS`/`AGENTS` once: the objects stay the same, only their backend changes.
"""
from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class _InlineBackend:
    """Runs the callable immediately on the caller's thread."""

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        fut: Future = Future()
        try:
            fut.set_result(fn(*args, **kwargs))
        except BaseException as e:  # noqa: BLE001 - delivered through the future
            fut.set_exception(e)
        return fut

    def shutdown(self, wait: bool = True) -> None:
        return None


class _SwitchableExecutor:
    def __init__(self, name: str, workers: int):
        self.name = name
        self.workers = workers
        self._lock = threading.Lock()
        self._backend: Any = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=name)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        return self._backend.submit(fn, *args, **kwargs)

    def use_inline(self) -> None:
        with self._lock:
            old, self._backend = self._backend, _InlineBackend()
        old.shutdown(wait=False)

    def use_threads(self) -> None:
        with self._lock:
            old = self._backend
            self._backend = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix=self.name)
        old.shutdown(wait=False)

    @property
    def inline(self) -> bool:
        return isinstance(self._backend, _InlineBackend)


JOBS = _SwitchableExecutor("jobs", 8)
AGENTS = _SwitchableExecutor("agents", 4)


def use_inline_executors() -> None:
    """Tests: run JOBS and AGENTS synchronously on the caller's thread."""
    JOBS.use_inline()
    AGENTS.use_inline()


def use_thread_executors() -> None:
    """Restore real thread pools (fresh ones)."""
    JOBS.use_threads()
    AGENTS.use_threads()


def on_agents_thread() -> bool:
    return threading.current_thread().name.startswith(AGENTS.name)
