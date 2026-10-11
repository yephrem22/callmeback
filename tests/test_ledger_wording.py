"""Spec 007 research R9: call times read as 12-hour Chicago time, matching the dashboard."""
from __future__ import annotations

from app import engine, ledger
from app.state import HoldReason, Status
from tests.helpers import drive_to, make_verification

EVENING = "2026-10-11T01:46:00Z"          # 8:46 PM CDT on Oct 10
MORNING = "2026-10-10T14:05:00Z"          # 9:05 AM CDT


def _stamp(db, ver_id: str, ts: str) -> None:
    db.execute("UPDATE verifications SET updated_at=? WHERE id=?", (ts, ver_id))


def test_clock_format():
    assert ledger._chicago_hhmm(EVENING) == "8:46 PM"
    assert ledger._chicago_hhmm(MORNING) == "9:05 AM"
    assert ledger._chicago_hhmm(None) == "unknown time"


def test_denied_reason_reads_12_hour(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    ver = make_verification(db, iid, final_label="DENIED", source="twilio", digits="2", det_label="NO")
    _stamp(db, ver, EVENING)
    assert ledger.can_release(iid, conn=db)[1] == "invoice is HELD (vendor denied the change on the 8:46 PM call)"


def test_confirmed_reason_reads_12_hour(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.CONFIRMED)
    ver = make_verification(db, iid, final_label="CONFIRMED", source="twilio", digits="1", det_label="YES", last4_ok=1)
    _stamp(db, ver, MORNING)
    ok, reason = ledger.can_release(iid, conn=db)
    assert ok and reason == "vendor confirmed by keypad on the 9:05 AM call"
