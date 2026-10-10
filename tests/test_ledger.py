"""PLAN.md §13.1 release eligibility, one payment per invoice, hold and review."""
from __future__ import annotations

from datetime import date

import pytest

from app import engine, ledger, repo
from app.ledger import PolicyViolation
from app.state import HoldReason, IllegalTransition, Status
from tests.helpers import drive_to, make_verification


def _ingest(db, name):
    return engine.ingest_sample(name, conn=db)


def _events(db, iid):
    return [r[0] for r in db.execute("SELECT event FROM audit_log WHERE subject_id=? ORDER BY seq", (iid,)).fetchall()]


# ---- can_release matrix ------------------------------------------------------

@pytest.mark.parametrize("status", list(Status))
def test_can_release_matrix_green_invoice(db, status):
    iid = _ingest(db, "01_acme_normal")          # AUTO_APPROVED, GREEN/AUTO_RELEASE
    if status is Status.HELD:
        drive_to(db, iid, Status.HELD, HoldReason.AGENT_HOLD)
    elif status is not Status.AUTO_APPROVED:
        try:
            drive_to(db, iid, status)
        except ValueError:
            pytest.skip(f"{status} unreachable from AUTO_APPROVED")
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is (status is Status.AUTO_APPROVED), reason
    assert isinstance(reason, str) and reason


@pytest.mark.parametrize("status", [s for s in Status if s not in (Status.HELD,)])
def test_can_release_matrix_callback_invoice(db, status):
    iid = _ingest(db, "03_heartland_bank_change")   # CALL_PENDING, RED/CALLBACK, bank_changed
    try:
        drive_to(db, iid, status)
    except ValueError:
        pytest.skip(f"{status} unreachable from CALL_PENDING")
    if status is Status.CONFIRMED:
        make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, digits="1")
    ok, _ = ledger.can_release(iid, conn=db)
    assert ok is (status is Status.CONFIRMED)


def test_confirmed_requires_verification_rules(db):
    iid = _ingest(db, "03_heartland_bank_change")
    drive_to(db, iid, Status.CONFIRMED)
    assert ledger.can_release(iid, conn=db) == (False, "CONFIRMED but no verification record exists")
    make_verification(db, iid, final_label="DENIED")
    assert ledger.can_release(iid, conn=db)[0] is False
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=None, digits="1")
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is False and "last-four" in reason
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=0, digits="1")
    assert ledger.can_release(iid, conn=db)[0] is False
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, digits="1")
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is True and "keypad" in reason and "simulated" in reason


def test_simulated_source_rejected_outside_demo_mode(demo_mode_off):
    db = demo_mode_off
    iid = _ingest(db, "03_heartland_bank_change")
    drive_to(db, iid, Status.CONFIRMED)
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, source="simulated")
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is False and "DEMO_MODE" in reason
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, source="twilio")
    assert ledger.can_release(iid, conn=db)[0] is True


def test_review_approved_requires_approve_decision(db):
    iid = _ingest(db, "04_prairie_review")        # NEEDS_REVIEW
    assert ledger.can_release(iid, conn=db)[0] is False
    assert ledger.record_review(iid, "approve", "ok", conn=db) == "REVIEW_APPROVED"
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is True and "reviewer" in reason
    assert "review_decision" in _events(db, iid)
    assert repo.get_invoice(db, iid)["review"]["decision"] == "approve"


def test_review_reject_holds(db):
    iid = _ingest(db, "04_prairie_review")
    assert ledger.record_review(iid, "reject", "looks off", conn=db) == "HELD"
    inv = repo.get_invoice(db, iid)
    assert (inv["status"], inv["hold_reason"]) == ("HELD", "REVIEW_REJECTED")
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok is False and "reviewer rejected" in reason


def test_review_from_wrong_state_raises(db):
    iid = _ingest(db, "01_acme_normal")
    with pytest.raises(IllegalTransition):
        ledger.record_review(iid, "approve", conn=db)
    with pytest.raises(ValueError):
        ledger.record_review(_ingest(db, "04_prairie_review"), "maybe", conn=db)


# ---- release ------------------------------------------------------------------

def test_release_green_invoice_pays_vendor_master_once(db):
    iid = _ingest(db, "01_acme_normal")
    pay_id = ledger.release(iid, by="policy:auto", conn=db)
    pay = repo.get_payment(db, iid)
    assert pay["id"] == pay_id and pay["amount_cents"] == 1215000
    assert (pay["bank_name"], pay["routing"], pay["account"]) == ("Plains Federal Bank", "123456780", "4421984821")
    assert pay["method"] == "ACH-CCD" and pay["released_by"] == "policy:auto"
    assert date.fromisoformat(pay["effective_date"]).weekday() < 5
    assert repo.get_invoice(db, iid)["status"] == "RELEASED"
    assert _events(db, iid)[-2:] == ["status_changed", "payment_released"]
    with pytest.raises(PolicyViolation):
        ledger.release(iid, by="policy:auto", conn=db)
    assert db.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?", (iid,)).fetchone()[0] == 1


def test_release_from_held_raises_and_audits(db):
    iid = _ingest(db, "02_acme_fraud")
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    with pytest.raises(PolicyViolation) as e:
        ledger.release(iid, by="agent:payments", conn=db)
    assert "HELD" in str(e.value) and "vendor denied" in str(e.value)
    assert repo.get_payment(db, iid) is None
    assert "release_blocked" in _events(db, iid)
    assert repo.get_invoice(db, iid)["status"] == "HELD"


def test_fraud_invoice_can_never_pay_the_email_account(db):
    iid = _ingest(db, "02_acme_fraud")
    drive_to(db, iid, Status.CONFIRMED)
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, digits="1")
    # Even if someone forged a confirmed verification, the destination is the vendor master.
    ledger.release(iid, by="agent:payments", conn=db)
    pay = repo.get_payment(db, iid)
    assert pay["routing"] == "123456780" and pay["account"] == "4421984821"
    assert pay["account"] != "7730019942"


def test_release_requires_vendor_record(db):
    iid = _ingest(db, "05_unknown_vendor")        # HELD(UNKNOWN_VENDOR)
    with pytest.raises(PolicyViolation):
        ledger.release(iid, by="policy:auto", conn=db)


def test_next_business_day():
    assert ledger.next_business_day(date(2026, 10, 9)) == date(2026, 10, 12)   # Fri → Mon
    assert ledger.next_business_day(date(2026, 10, 10)) == date(2026, 10, 12)  # Sat → Mon
    assert ledger.next_business_day(date(2026, 10, 12)) == date(2026, 10, 13)  # Mon → Tue


def test_audit_actor_mapping():
    assert ledger.audit_actor("policy:auto") == "policy"
    assert ledger.audit_actor("agent:payments") == "agent:payments"
    assert ledger.audit_actor("agent:payments:redteam") == "agent:payments"
    assert ledger.audit_actor("whoever") == "system"


# ---- hold ---------------------------------------------------------------------

def test_hold_is_idempotent(db):
    iid = _ingest(db, "01_acme_normal")
    assert ledger.hold(iid, "agent not comfortable", conn=db) is True
    inv = repo.get_invoice(db, iid)
    assert (inv["status"], inv["hold_reason"]) == ("HELD", "AGENT_HOLD")
    assert ledger.hold(iid, "again", conn=db) is False
    assert repo.get_invoice(db, iid)["version"] == inv["version"]
    assert _events(db, iid).count("hold_confirmed") == 1
    with pytest.raises(PolicyViolation):
        ledger.release(iid, by="agent:payments", conn=db)


def test_hold_from_non_releasable_state_raises(db):
    iid = _ingest(db, "03_heartland_bank_change")   # CALL_PENDING
    with pytest.raises(IllegalTransition):
        ledger.hold(iid, "nope", conn=db)


def test_retry_callback_allowed(db):
    iid = _ingest(db, "02_acme_fraud")
    drive_to(db, iid, Status.HELD, HoldReason.NO_ANSWER)
    assert ledger.retry_callback_allowed(iid, conn=db) is True
    iid2 = _ingest(db, "02_acme_fraud")
    drive_to(db, iid2, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    assert ledger.retry_callback_allowed(iid2, conn=db) is False


@pytest.mark.parametrize("status", list(Status))
def test_can_release_every_status_forced(db, status):
    """Force each status directly (bypassing transitions) on a GREEN invoice with a
    CONFIRMED last4-ok verification present: only the three §13.1 rows release."""
    iid = _ingest(db, "01_acme_normal")
    make_verification(db, iid, final_label="CONFIRMED", last4_ok=1, digits="1")
    db.execute("UPDATE invoices SET review=? WHERE id=?", ('{"decision":"approve","note":"","at":"x"}', iid))
    db.execute("UPDATE invoices SET status=?, hold_reason=? WHERE id=?",
               (status.value, "AGENT_HOLD" if status is Status.HELD else None, iid))
    ok, reason = ledger.can_release(iid, conn=db)
    if status is Status.AUTO_APPROVED or status is Status.CONFIRMED:
        assert ok is True, reason
    elif status is Status.REVIEW_APPROVED:
        assert ok is False and "REVIEW action" in reason      # action is AUTO_RELEASE, not REVIEW
    else:
        assert ok is False, reason
    if not ok:
        with pytest.raises(PolicyViolation):
            ledger.release(iid, by="policy:auto", conn=db)
        assert repo.get_payment(db, iid) is None
