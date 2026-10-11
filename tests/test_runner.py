"""The time-boxed agent runner (FR-009, FR-013, SC-006; analyze C2, E1)."""
from __future__ import annotations

import threading
import time

import pytest
from strands.types.exceptions import StructuredOutputException

from app import ai_mode, audit, executors, repo
from app.agents import runner
from app.ids import new_id


def _invoice(db) -> str:
    iid = new_id("inv_")
    repo.insert_invoice(db, id=iid, source="sample", raw_sha256="x", body_text="b")
    return iid


def _traces(db, iid):
    return [tuple(r) for r in db.execute(
        "SELECT agent, kind, summary FROM agent_traces WHERE subject_id=? ORDER BY id", (iid,)).fetchall()]


@pytest.fixture
def live():
    ai_mode.set_ai_mode("live", record=False)
    yield
    ai_mode.reset_override()


@pytest.fixture
def threads():
    executors.use_thread_executors()
    yield
    executors.use_inline_executors()


def test_ai_off_returns_fallback_without_calling(db):
    iid = _invoice(db)
    called = []
    result, outcome = runner.run_agent("analyst", iid, lambda ctx: called.append(1) or "model", 5, lambda: "rules")
    assert (result, outcome) == ("rules", "fallback") and called == []
    assert _traces(db, iid) == [("analyst", "fallback", "AI off")]


def test_result_when_model_answers(db, live):
    iid = _invoice(db)
    result, outcome = runner.run_agent("analyst", iid, lambda ctx: f"ok {ctx.run_id[:4]}", 5, lambda: "rules")
    assert outcome == "result" and result == "ok run_"
    assert db.execute("SELECT ai_fallback FROM invoices WHERE id=?", (iid,)).fetchone()[0] == 0


def test_timeout_falls_back_quickly_and_cancels_the_run(db, live, threads):
    iid = _invoice(db)
    stopped = threading.Event()
    acted_after_timeout = []

    def slow(ctx):
        while not ctx.cancel.is_set():
            time.sleep(0.02)
        stopped.set()
        if not ctx.cancel.is_set():  # a closure-bound tool would check exactly this
            acted_after_timeout.append(1)
        return "late"

    t0 = time.perf_counter()
    result, outcome = runner.run_agent("payments", iid, slow, 0.3, lambda: "rules")
    elapsed = time.perf_counter() - t0
    assert (result, outcome) == ("rules", "fallback")
    assert elapsed < 0.3 + 1.0                       # SC-006: fallback within timeout + 1 s
    assert stopped.wait(2.0)                          # analyze C2: the run stops and frees its thread
    assert acted_after_timeout == []
    kinds = [k for _, k, _ in _traces(db, iid)]
    assert kinds == ["fallback"]
    assert "timed out" in _traces(db, iid)[0][2]
    assert db.execute("SELECT ai_fallback FROM invoices WHERE id=?", (iid,)).fetchone()[0] == 1
    assert "ai_fallback" in [e["event"] for e in audit.list_entries(iid, conn=db)]


def test_late_result_is_discarded(db, live, threads):
    iid = _invoice(db)
    finished = threading.Event()

    def slow_ignoring_cancel(ctx):
        time.sleep(0.5)
        finished.set()
        return "late"

    result, outcome = runner.run_agent("analyst", iid, slow_ignoring_cancel, 0.1, lambda: "rules")
    assert (result, outcome) == ("rules", "fallback")
    assert finished.wait(2.0)
    time.sleep(0.05)
    assert [k for _, k, _ in _traces(db, iid)] == ["fallback"]


@pytest.mark.parametrize("exc", [RuntimeError("model exploded"), StructuredOutputException("bad output")])
def test_exceptions_fall_back(db, live, exc):
    iid = _invoice(db)

    def boom(ctx):
        raise exc

    result, outcome = runner.run_agent("intake", iid, boom, 5, lambda: None)
    assert (result, outcome) == (None, "fallback")
    summary = _traces(db, iid)[0][2]
    assert type(exc).__name__ in summary


def test_refuses_to_run_on_an_agents_thread(db, live, threads):
    iid = _invoice(db)
    errors = []

    def inner():
        try:
            runner.run_agent("analyst", iid, lambda ctx: "x", 1, lambda: "rules")
        except RuntimeError as e:
            errors.append(str(e))

    executors.AGENTS.submit(inner).result(timeout=5)
    assert errors and "deadlock" in errors[0]


def test_start_agent_runs_on_jobs_and_calls_on_done(db, live, threads):
    iid = _invoice(db)
    got = []
    done = threading.Event()
    fut = runner.start_agent("analyst", iid, lambda ctx: "model", 5, lambda: "rules",
                             on_done=lambda r, o: (got.append((r, o, threading.current_thread().name)), done.set()))
    fut.result(timeout=5)
    assert done.wait(5)
    assert got[0][:2] == ("model", "result")
    assert got[0][2].startswith("jobs")


def test_change_case_subject_does_not_touch_invoices(db, live):
    result, outcome = runner.run_agent("verifier", "cc_123", lambda ctx: (_ for _ in ()).throw(RuntimeError("x")), 1,
                                       lambda: "UNCLEAR")
    assert (result, outcome) == ("UNCLEAR", "fallback")
