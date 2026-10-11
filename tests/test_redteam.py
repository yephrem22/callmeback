"""PLAN.md §11.5 / §17.1: "Try to make the AI pay" must never release money."""
from __future__ import annotations

import pytest

from app import ai_mode, engine, repo
from app.agents.redteam import RedteamRefused, redteam
from app.state import HoldReason, Status
from tests.fakes import ScriptedModel, text_turn, tool_turn
from tests.helpers import drive_to


@pytest.fixture
def held_fraud(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    return iid


@pytest.fixture
def live():
    ai_mode.set_ai_mode("live", record=False)
    yield
    ai_mode.reset_override()


def _payments(db) -> int:
    return db.execute("SELECT COUNT(*) FROM payments").fetchone()[0]


def _kinds(db, iid):
    return [r[0] for r in db.execute("SELECT kind FROM agent_traces WHERE subject_id=? ORDER BY id", (iid,)).fetchall()]


def test_compromised_agent_that_calls_release_is_blocked_by_the_plugin(db, held_fraud, live, fake_model):
    model = fake_model(ScriptedModel([tool_turn("release_payment"), text_turn("Released as the CFO asked.")]))
    out = redteam(held_fraud)
    assert out["blocked"] is True and out["layer"] == "plugin"
    assert "HELD" in out["reason"] and out["run_id"].startswith("run_")
    assert "guard_block" in _kinds(db, held_fraud)
    assert _payments(db) == 0
    assert "This is the CFO" in model.prompt_text()


def test_agent_that_calls_no_tool_triggers_one_direct_guarded_attempt(db, held_fraud, live, fake_model):
    fake_model(ScriptedModel([text_turn("I refuse to release this payment.")]))
    out = redteam(held_fraud)
    assert out["blocked"] is True and out["layer"] in {"plugin", "ledger"}
    assert _payments(db) == 0
    assert repo.get_invoice(db, held_fraud)["status"] == "HELD"


def test_ai_off_makes_only_the_direct_attempt(db, held_fraud):
    out = redteam(held_fraud)
    # research R9: Strands 1.59.0 runs plugin hooks on direct tool calls, so the guard itself blocks
    assert out["blocked"] is True and out["layer"] == "plugin"
    assert "None" not in out["reason"] and "vendor denied the change" in out["reason"]
    assert _payments(db) == 0


def test_releasable_invoice_is_refused_and_nothing_is_built(db, live, fake_model):
    iid = engine.ingest_sample("01_acme_normal", conn=db)       # AUTO_APPROVED: releasable
    model = fake_model(ScriptedModel([tool_turn("release_payment")]))
    traces_before = db.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0]
    audit_before = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    with pytest.raises(RedteamRefused):
        redteam(iid)
    assert db.execute("SELECT COUNT(*) FROM agent_traces").fetchone()[0] == traces_before
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == audit_before
    assert model.calls == [] and _payments(db) == 0


def test_two_runs_in_a_row_still_pay_nothing(db, held_fraud, live, fake_model):
    for _ in range(2):
        fake_model(ScriptedModel([tool_turn("release_payment"), tool_turn("release_payment"), text_turn("ok")]))
        assert redteam(held_fraud)["blocked"] is True
    assert _payments(db) == 0
