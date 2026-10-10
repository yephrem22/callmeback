"""PLAN.md §7.3: every legal transition, every illegal one, idempotent repeats,
hold-reason rules, retry rules, terminal states."""
from __future__ import annotations

import itertools

import pytest

from app import repo
from app.ids import new_id
from app.state import (ALLOWED, HOLD_REASONS_FROM, RETRYABLE, HoldReason, IllegalTransition, Status,
                       transition)

ALL = list(Status)


def _invoice(db, status: Status, hold_reason: HoldReason | None = None) -> str:
    iid = new_id("inv_")
    repo.insert_invoice(db, id=iid, source="sample", raw_sha256="x", body_text="b",
                        status=status.value, hold_reason=hold_reason.value if hold_reason else None)
    return iid


def _audit_count(db, iid: str) -> int:
    return db.execute("SELECT COUNT(*) FROM audit_log WHERE subject_id=? AND event='status_changed'",
                      (iid,)).fetchone()[0]


LEGAL = [(f, t) for f, tos in ALLOWED.items() for t in tos if t is not Status.HELD]


@pytest.mark.parametrize("frm,to", LEGAL, ids=[f"{f}->{t}" for f, t in LEGAL])
def test_every_legal_non_hold_transition(db, frm, to):
    reason = HoldReason.NO_ANSWER if frm is Status.HELD else None
    iid = _invoice(db, frm, reason)
    assert transition(iid, to, actor="system") is True
    inv = repo.get_invoice(db, iid)
    assert inv["status"] == to.value
    assert inv["hold_reason"] is None
    assert inv["version"] == 1
    assert _audit_count(db, iid) == 1


HELD_LEGAL = [(f, r) for f, rs in HOLD_REASONS_FROM.items() for r in rs]


@pytest.mark.parametrize("frm,reason", HELD_LEGAL, ids=[f"{f}->HELD({r})" for f, r in HELD_LEGAL])
def test_every_legal_hold(db, frm, reason):
    iid = _invoice(db, frm)
    assert transition(iid, Status.HELD, hold_reason=reason, actor="policy") is True
    inv = repo.get_invoice(db, iid)
    assert inv["status"] == "HELD" and inv["hold_reason"] == reason.value
    assert _audit_count(db, iid) == 1


ILLEGAL = [(f, t) for f, t in itertools.product(ALL, ALL)
           if t not in ALLOWED[f] and f != t and t is not Status.HELD]


@pytest.mark.parametrize("frm,to", ILLEGAL, ids=[f"{f}->{t}" for f, t in ILLEGAL])
def test_every_illegal_transition_raises(db, frm, to):
    iid = _invoice(db, frm, HoldReason.NO_ANSWER if frm is Status.HELD else None)
    with pytest.raises(IllegalTransition):
        transition(iid, to, actor="system")
    assert repo.get_invoice(db, iid)["status"] == frm.value
    assert _audit_count(db, iid) == 0


HELD_ILLEGAL = [(f, r) for f in ALL for r in HoldReason
                if r not in HOLD_REASONS_FROM.get(f, set()) and f is not Status.HELD]


@pytest.mark.parametrize("frm,reason", HELD_ILLEGAL, ids=[f"{f}->HELD({r})" for f, r in HELD_ILLEGAL])
def test_every_illegal_hold_raises(db, frm, reason):
    iid = _invoice(db, frm)
    with pytest.raises(IllegalTransition):
        transition(iid, Status.HELD, hold_reason=reason, actor="policy")
    assert repo.get_invoice(db, iid)["status"] == frm.value
    assert _audit_count(db, iid) == 0


def test_held_to_held_with_different_reason_is_illegal(db):
    iid = _invoice(db, Status.HELD, HoldReason.NO_ANSWER)
    with pytest.raises(IllegalTransition):
        transition(iid, Status.HELD, hold_reason=HoldReason.AGENT_HOLD, actor="policy")
    assert transition(iid, Status.HELD, hold_reason=HoldReason.NO_ANSWER, actor="policy") is False


def test_bad_status_string_raises_illegal_transition(db):
    iid = _invoice(db, Status.RECEIVED)
    with pytest.raises(IllegalTransition):
        transition(iid, "CONFIRMD", actor="system")
    with pytest.raises(IllegalTransition):
        transition(iid, Status.HELD, hold_reason="NOPE", actor="system")


def test_transition_with_autocommit_connection_is_still_atomic(db):
    """A failing audit write must roll back the status change (§7.3)."""
    iid = _invoice(db, Status.RECEIVED)
    assert not db.in_transaction
    with pytest.raises(ValueError):
        transition(iid, Status.EXTRACTED, actor="not-an-actor", conn=db)
    assert repo.get_invoice(db, iid)["status"] == "RECEIVED"
    assert _audit_count(db, iid) == 0
    assert not db.in_transaction


def test_transition_joins_callers_transaction(db):
    from app.db import tx
    iid = _invoice(db, Status.RECEIVED)
    with tx(db):
        assert transition(iid, Status.EXTRACTED, actor="system", conn=db) is True
        assert db.in_transaction
    assert repo.get_invoice(db, iid)["status"] == "EXTRACTED"


def test_repeat_is_noop_returning_false(db):
    iid = _invoice(db, Status.RECEIVED)
    assert transition(iid, Status.EXTRACTED, actor="system") is True
    assert transition(iid, Status.EXTRACTED, actor="system") is False
    inv = repo.get_invoice(db, iid)
    assert inv["version"] == 1
    assert _audit_count(db, iid) == 1


def test_held_without_reason_raises(db):
    iid = _invoice(db, Status.CALLING)
    with pytest.raises(IllegalTransition):
        transition(iid, Status.HELD, actor="twilio")


def test_held_with_reason_not_allowed_for_from_state_raises(db):
    iid = _invoice(db, Status.SCORED)
    with pytest.raises(IllegalTransition):
        transition(iid, Status.HELD, hold_reason=HoldReason.DENIED_BY_VENDOR, actor="policy")
    iid2 = _invoice(db, Status.CALL_PENDING)
    with pytest.raises(IllegalTransition):
        transition(iid2, Status.HELD, hold_reason=HoldReason.DENIED_BY_VENDOR, actor="policy")


def test_reason_on_non_held_target_raises(db):
    iid = _invoice(db, Status.SCORED)
    with pytest.raises(IllegalTransition):
        transition(iid, Status.CALL_PENDING, hold_reason=HoldReason.NO_ANSWER, actor="policy")


@pytest.mark.parametrize("reason", list(HoldReason))
def test_retry_from_held_only_for_retryable_reasons(db, reason):
    iid = _invoice(db, Status.HELD, reason)
    if reason in RETRYABLE:
        assert transition(iid, Status.CALL_PENDING, actor="system") is True
        assert repo.get_invoice(db, iid)["hold_reason"] is None
    else:
        with pytest.raises(IllegalTransition):
            transition(iid, Status.CALL_PENDING, actor="system")


@pytest.mark.parametrize("terminal", [Status.RELEASED, Status.FAILED])
@pytest.mark.parametrize("to", ALL)
def test_terminal_states_accept_nothing(db, terminal, to):
    iid = _invoice(db, terminal)
    if to == terminal:
        assert transition(iid, to, actor="system") is False
        return
    with pytest.raises(IllegalTransition):
        transition(iid, to, hold_reason=HoldReason.AGENT_HOLD if to is Status.HELD else None, actor="system")


def test_version_increments_per_transition(db):
    iid = _invoice(db, Status.RECEIVED)
    for to in (Status.EXTRACTED, Status.SCORED, Status.CALL_PENDING, Status.CALLING):
        transition(iid, to, actor="system")
    assert repo.get_invoice(db, iid)["version"] == 4
    assert _audit_count(db, iid) == 4


def test_unknown_invoice_raises(db):
    with pytest.raises(IllegalTransition):
        transition("inv_nope", Status.EXTRACTED, actor="system")
