"""PLAN.md §8.4: the five samples must produce exactly these flags, points,
tier and action with AI off, through the real ingest path."""
from __future__ import annotations

import time

import pytest

from app import engine, repo
from app.policy.engine import amount_ratio

VECTORS = {
    "01_acme_normal": (set(), 0, "GREEN", "AUTO_RELEASE", "AUTO_APPROVED", None, "ven_acme", "KNOWN"),
    "02_acme_fraud": ({("LOOKALIKE_DOMAIN", 40), ("BANK_CHANGED", 50), ("REPLY_TO_MISMATCH", 20),
                       ("AMOUNT_3X", 25), ("URGENCY", 10), ("AVOID_VERIFICATION", 15),
                       ("AI_DIRECTED_TEXT", 0), ("PHONE_IN_EMAIL", 0)},
                      160, "RED", "CALLBACK", "CALL_PENDING", None, "ven_acme", "LOOKALIKE"),
    "03_heartland_bank_change": ({("BANK_CHANGED", 50)}, 50, "RED", "CALLBACK", "CALL_PENDING", None,
                                 "ven_heartland", "KNOWN"),
    "04_prairie_review": ({("AMOUNT_2X", 15), ("URGENCY", 10)}, 25, "YELLOW", "REVIEW", "NEEDS_REVIEW", None,
                          "ven_prairie", "KNOWN"),
    "05_unknown_vendor": ({("UNKNOWN_VENDOR", 30), ("INVALID_ROUTING", 30)}, 60, "RED", "HOLD_MANUAL",
                          "HELD", "UNKNOWN_VENDOR", None, "NO_VENDOR"),
}


@pytest.mark.parametrize("name", list(VECTORS))
def test_sample_vector(db, name):
    flags, points, tier, action, status, hold_reason, vendor_id, sender_status = VECTORS[name]
    t0 = time.perf_counter()
    iid = engine.ingest_sample(name, conn=db)
    assert time.perf_counter() - t0 < 1.0
    risk = repo.get_risk(db, iid)
    assert {(f.code, f.points) for f in risk.flags} == flags
    assert len(risk.flags) == len(flags)                      # each flag fires at most once
    assert (risk.points, risk.tier, risk.action) == (points, tier, action)
    assert risk.vendor_id == vendor_id and risk.sender_status == sender_status
    assert risk.policy_version == "2026-10-10.1"
    inv = repo.get_invoice(db, iid)
    assert (inv["status"], inv["hold_reason"]) == (status, hold_reason)
    assert inv["vendor_id"] == vendor_id
    events = {r[0] for r in db.execute("SELECT event FROM audit_log WHERE subject_id=?", (iid,)).fetchall()}
    assert {"invoice_received", "extraction_done", "vendor_resolved", "risk_scored", "status_changed"} <= events


def test_fraud_details(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    risk = repo.get_risk(db, iid)
    by = {f.code: f for f in risk.flags}
    assert by["LOOKALIKE_DOMAIN"].detail == "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')"
    assert "4.1" in by["AMOUNT_3X"].title and amount_ratio(risk) == 4.06
    assert by["REPLY_TO_MISMATCH"].detail.startswith("Replies go to gmail.com")
    assert set(by["URGENCY"].evidence) == {"today", "immediately", "urgent"}
    assert "skip the callback" in by["AVOID_VERIFICATION"].evidence
    assert by["AI_DIRECTED_TEXT"].evidence == ["note for automated"]
    assert by["PHONE_IN_EMAIL"].evidence == ["(816) 555-0142"]
    assert risk.bank_changed is True
    assert (risk.proposed_bank_name, risk.proposed_routing, risk.proposed_account) == \
        ("First Coastal Trust", "061100059", "7730019942")
    assert risk.amount_cents == 4875000 and risk.median_cents == 1202000
    # masked evidence only: the full account number never appears in the flag text
    assert all("7730019942" not in (f.detail + " ".join(f.evidence)) for f in risk.flags)


def test_prairie_and_normal_details(db):
    iid = engine.ingest_sample("04_prairie_review", conn=db)
    risk = repo.get_risk(db, iid)
    by = {f.code: f for f in risk.flags}
    assert "2.1" in by["AMOUNT_2X"].title and amount_ratio(risk) == 2.1
    assert risk.bank_changed is False and risk.proposed_routing is None
    iid1 = engine.ingest_sample("01_acme_normal", conn=db)
    r1 = repo.get_risk(db, iid1)
    assert r1.flags == [] and r1.bank_changed is False and amount_ratio(r1) == 1.01


def test_scoring_is_deterministic(db):
    a = repo.get_risk(db, engine.ingest_sample("02_acme_fraud", conn=db))
    b = repo.get_risk(db, engine.ingest_sample("02_acme_fraud", conn=db))
    assert a.model_dump() == b.model_dump()


def test_unknown_sample_raises(db):
    with pytest.raises(FileNotFoundError):
        engine.ingest_sample("99_nope", conn=db)
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0


def test_no_bank_details_flag_for_known_vendor(db):
    raw = (b"From: billing@acme-supply.com\nTo: ap@northgate-mfg.example\nSubject: Invoice INV-9\n\n"
           b"Invoice number: INV-9\nAmount due: $12,000.00\nPlease pay to the account on file.\n")
    iid = engine.ingest_upload(raw, conn=db)
    risk = repo.get_risk(db, iid)
    assert [f.code for f in risk.flags] == ["NO_BANK_DETAILS"]
    assert risk.action == "AUTO_RELEASE" and risk.bank_changed is False


def test_unrecognized_sender_by_fuzzy_name(db):
    raw = (b'From: "Acme Supply Company Invoices" <ar@totally-different.net>\nTo: ap@x\nSubject: Invoice A-1\n\n'
           b"Invoice number: A-1\nAmount due: $12,000.00\nBank: Plains Federal Bank\nRouting number: 123456780\n"
           b"Account number: 4421984821\n")
    risk = repo.get_risk(db, engine.ingest_upload(raw, conn=db))
    assert risk.sender_status == "UNRECOGNIZED" and risk.vendor_id == "ven_acme"
    assert {f.code for f in risk.flags} == {"UNRECOGNIZED_SENDER"}
    assert (risk.points, risk.tier, risk.action) == (25, "YELLOW", "REVIEW")


def test_subdomain_is_known_and_extraction_mismatch_is_zero_points(db):
    raw = (b"From: billing@mail.acme-supply.com\nTo: ap@x\nSubject: Invoice A-2\n\n"
           b"Invoice number: A-2\nAmount due: $12,000.00\nBank: Plains Federal Bank\nRouting number: 123456780\n"
           b"Account number: 4421984821\nAccount number: 4421980000\n")
    risk = repo.get_risk(db, engine.ingest_upload(raw, conn=db))
    assert risk.sender_status == "KNOWN"
    assert {f.code for f in risk.flags} == {"BANK_CHANGED", "EXTRACTION_MISMATCH"} or \
        {f.code for f in risk.flags} == {"EXTRACTION_MISMATCH"}
    assert next(f for f in risk.flags if f.code == "EXTRACTION_MISMATCH").points == 0
