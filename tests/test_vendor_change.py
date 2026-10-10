"""Spec US3: the vendor master updates only after a confirmed bank change."""
from __future__ import annotations

import pytest

from app import engine, ledger, repo, seed
from app.ledger import PolicyViolation
from app.state import HoldReason, Status
from tests.helpers import drive_to, make_verification


def _heartland_confirmed(db, last4_ok=1):
    iid = engine.ingest_sample("03_heartland_bank_change", conn=db)
    drive_to(db, iid, Status.CONFIRMED)
    ver = make_verification(db, iid, final_label="CONFIRMED", last4_ok=last4_ok, digits="1")
    return iid, ver


def test_heartland_change_updates_master_and_history(db):
    iid, ver = _heartland_confirmed(db)
    assert ledger.apply_vendor_bank_change(iid, ver, conn=db) is True
    v = repo.get_vendor(db, "ven_heartland")
    assert (v["bank_name"], v["routing"], v["account"]) == ("Gateway National Bank", "044000105", "6620194455")
    hist = repo.vendor_bank_history(db, "ven_heartland")
    assert len(hist) == 1
    h = hist[0]
    assert (h["old_bank_name"], h["old_routing"], h["old_account"]) == ("River City Bank", "102030402", "5512003377")
    assert (h["new_bank_name"], h["new_routing"], h["new_account"]) == ("Gateway National Bank", "044000105", "6620194455")
    assert (h["invoice_id"], h["verification_id"]) == (iid, ver)
    import json
    row = db.execute("SELECT data FROM audit_log WHERE event='vendor_bank_updated' AND subject_id=?", (iid,)).fetchone()
    assert row is not None
    data = json.loads(row[0])
    assert "River City Bank ••••3377 → Gateway National Bank ••••4455 (verified by callback" in data["message"]
    assert "5512003377" not in row[0] and "6620194455" not in row[0]
    assert data["old_account"] == "••••3377" and data["new_account"] == "••••4455"
    assert data["new_routing"] == "044000105"
    # idempotent
    assert ledger.apply_vendor_bank_change(iid, ver, conn=db) is False
    assert len(repo.vendor_bank_history(db, "ven_heartland")) == 1


def test_release_after_change_pays_the_new_account(db):
    iid, ver = _heartland_confirmed(db)
    ledger.apply_vendor_bank_change(iid, ver, conn=db)
    ledger.release(iid, by="agent:payments", conn=db)
    pay = repo.get_payment(db, iid)
    assert (pay["bank_name"], pay["routing"], pay["account"]) == ("Gateway National Bank", "044000105", "6620194455")
    assert pay["amount_cents"] == 412000


def test_change_refused_without_last4_or_wrong_state(db):
    iid, ver = _heartland_confirmed(db, last4_ok=0)
    with pytest.raises(PolicyViolation):
        ledger.apply_vendor_bank_change(iid, ver, conn=db)
    v = repo.get_vendor(db, "ven_heartland")
    assert v["bank_name"] == "River City Bank" and repo.vendor_bank_history(db, "ven_heartland") == []

    iid2 = engine.ingest_sample("03_heartland_bank_change", conn=db)   # CALL_PENDING, not CONFIRMED
    ver2 = make_verification(db, iid2, final_label="CONFIRMED", last4_ok=1, digits="1")
    with pytest.raises(PolicyViolation):
        ledger.apply_vendor_bank_change(iid2, ver2, conn=db)

    iid3 = engine.ingest_sample("01_acme_normal", conn=db)             # no bank change requested
    drive_to(db, iid3, Status.RELEASED)
    with pytest.raises(PolicyViolation):
        ledger.apply_vendor_bank_change(iid3, ver, conn=db)


def test_change_refused_when_verification_belongs_elsewhere(db):
    iid, _ = _heartland_confirmed(db)
    other = engine.ingest_sample("02_acme_fraud", conn=db)
    foreign = make_verification(db, other, final_label="CONFIRMED", last4_ok=1, digits="1")
    with pytest.raises(PolicyViolation):
        ledger.apply_vendor_bank_change(iid, foreign, conn=db)


def test_denied_fraud_leaves_acme_untouched(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    make_verification(db, iid, final_label="DENIED", speech="No, we never changed banks", det_label="NO")
    v = repo.get_vendor(db, "ven_acme")
    assert (v["bank_name"], v["routing"], v["account"]) == ("Plains Federal Bank", "123456780", "4421984821")
    assert repo.vendor_bank_history(db, "ven_acme") == []


def test_reset_restores_heartland(db):
    iid, ver = _heartland_confirmed(db)
    ledger.apply_vendor_bank_change(iid, ver, conn=db)
    seed.reset_demo_data(db)
    v = repo.get_vendor(db, "ven_heartland")
    assert (v["bank_name"], v["routing"], v["account"]) == ("River City Bank", "102030402", "5512003377")
    assert repo.vendor_bank_history(db, "ven_heartland") == []
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0
