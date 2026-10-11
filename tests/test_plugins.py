"""Payment guard, trace and rate-limit plugins on a real Strands Agent with a scripted model (FR-007, FR-011, FR-012)."""
from __future__ import annotations

import pytest
from strands import Agent, tool
from strands.types.exceptions import ModelThrottledException

from app import audit, engine
from app.agents import plugins
from app.agents.plugins import PaymentGuardPlugin, RateLimitPlugin, TracePlugin, agent_kwargs
from tests.fakes import ScriptedModel, raise_turn, text_turn, tool_turn


def _rows(db, iid):
    return [tuple(r) for r in db.execute(
        "SELECT kind, name, summary FROM agent_traces WHERE subject_id=? ORDER BY id", (iid,)).fetchall()]


def _release_stub(calls):
    @tool
    def release_payment() -> str:
        """Release the payment for this invoice."""
        calls.append("release")
        return "released"
    return release_payment


def _summary_stub():
    @tool
    def get_case_summary() -> dict:
        """Case summary."""
        return {"status": "x"}
    return get_case_summary


def test_guard_registers_its_hook():
    p = PaymentGuardPlugin("inv_x", run_id="run_1")
    assert p.hooks, "Plugin.__init__ was not called; the guard would be silently disabled"


def test_guard_blocks_release_on_ineligible_invoice(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)        # CALL_PENDING: not releasable
    calls: list[str] = []
    model = ScriptedModel([tool_turn("release_payment"), text_turn("I could not release it.")])
    agent = Agent(model=model, tools=[_release_stub(calls)], plugins=[PaymentGuardPlugin(iid, run_id="run_g1")],
                  **agent_kwargs())
    agent("Release it.")
    assert calls == []
    rows = _rows(db, iid)
    assert ("guard_block", "release_payment") in [(k, n) for k, n, _ in rows]
    events = [(e["actor"], e["event"]) for e in audit.list_entries(iid, conn=db)]
    assert ("plugin:payment-guard", "guard_blocked") in events
    # the model was told it was blocked
    assert "BLOCKED by payment policy" in model.prompt_text()


def test_guard_allows_release_on_eligible_invoice(db):
    iid = engine.ingest_sample("01_acme_normal", conn=db)       # AUTO_APPROVED, GREEN
    calls: list[str] = []
    model = ScriptedModel([tool_turn("release_payment"), text_turn("Released.")])
    agent = Agent(model=model, tools=[_release_stub(calls)], plugins=[PaymentGuardPlugin(iid, run_id="run_g2")],
                  **agent_kwargs())
    agent("Release it.")
    assert calls == ["release"]
    assert ("guard_allow", "release_payment") in [(k, n) for k, n, _ in _rows(db, iid)]
    assert ("plugin:payment-guard", "guard_allowed") in [(e["actor"], e["event"]) for e in audit.list_entries(iid, conn=db)]


def test_guard_ignores_other_tools(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    model = ScriptedModel([tool_turn("get_case_summary"), text_turn("ok")])
    agent = Agent(model=model, tools=[_summary_stub()], plugins=[PaymentGuardPlugin(iid, run_id="run_g3")], **agent_kwargs())
    agent("Summarise.")
    assert not [r for r in _rows(db, iid) if r[0].startswith("guard")]


def test_trace_plugin_records_a_run_in_order_with_masked_summaries(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)

    @tool
    def lookup(account: str) -> str:
        """Look up an account."""
        return "found"

    model = ScriptedModel([tool_turn("lookup", {"account": "7730019942"}), text_turn("done")])
    agent = Agent(model=model, tools=[lookup], plugins=[TracePlugin(iid, "analyst", "run_t1")], **agent_kwargs())
    agent("Go.")
    kinds = [k for k, _, _ in _rows(db, iid)]
    assert kinds[0] == "run_start" and kinds[-1] == "run_end"
    assert kinds.count("model_call") == 2 and kinds.count("tool_call") == 1
    assert kinds.index("tool_call") > kinds.index("model_call")
    summaries = " ".join(s or "" for _, _, s in _rows(db, iid))
    assert "7730019942" not in summaries and "••••9942" in summaries
    assert all(len(s or "") <= 200 for _, _, s in _rows(db, iid))


def _throttle(reset: str = "0"):
    class _Resp:
        headers = {"x-ratelimit-reset": reset}

    class _Cause(Exception):
        response = _Resp()

    exc = ModelThrottledException("Error code: 429 rate limit")
    exc.__cause__ = _Cause("429")
    return exc


def test_rate_limit_retries_once_and_honours_reset(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(plugins, "_sleep", sleeps.append)
    plugins.reset_bucket()
    model = ScriptedModel([raise_turn(_throttle("2")), text_turn("answered")])
    agent = Agent(model=model, plugins=[RateLimitPlugin()], **agent_kwargs())
    result = agent("Hi")
    assert "answered" in str(result)
    assert sleeps == [2.0]


def test_rate_limit_gives_up_after_three_retries(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(plugins, "_sleep", sleeps.append)
    plugins.reset_bucket()
    model = ScriptedModel([raise_turn(_throttle()) for _ in range(5)])
    agent = Agent(model=model, plugins=[RateLimitPlugin()], **agent_kwargs())
    with pytest.raises(ModelThrottledException):
        agent("Hi")
    assert len(sleeps) == plugins.MAX_RETRIES == 3


def test_default_reset_is_five_seconds_when_header_missing(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(plugins, "_sleep", sleeps.append)
    plugins.reset_bucket()
    model = ScriptedModel([raise_turn(ModelThrottledException("rate limit")), text_turn("ok")])
    Agent(model=model, plugins=[RateLimitPlugin()], **agent_kwargs())("Hi")
    assert sleeps == [5.0]


def test_builtin_strands_retries_are_disabled():
    kw = agent_kwargs()
    assert kw["retry_strategy"] is None and kw["callback_handler"] is None
    a = Agent(model=ScriptedModel([text_turn("x")]), **kw)
    assert a._retry_strategy._max_attempts == 1  # noqa: SLF001  (analyze C1: no hidden 6-attempt backoff)
