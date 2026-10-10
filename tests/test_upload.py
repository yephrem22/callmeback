"""Spec US5: uploading a real .eml runs the same rules as a sample."""
from __future__ import annotations

import pytest

from app import engine, repo


def test_upload_known_vendor_scores_green(db):
    raw = (b'From: "Acme Supply Co. Billing" <billing@acme-supply.com>\nTo: ap@northgate-mfg.example\n'
           b"Subject: Invoice INV-20450\nDate: Sat, 10 Oct 2026 09:00:00 -0500\n\n"
           b"Invoice number: INV-20450\nAmount due: $11,900.00\nDue date: November 10, 2026\n"
           b"Bank: Plains Federal Bank\nRouting number: 123456780\nAccount number: 4421984821\n")
    iid = engine.ingest_upload(raw, conn=db)
    inv = repo.get_invoice(db, iid)
    assert inv["source"] == "upload" and inv["sample_name"] is None and len(inv["raw_sha256"]) == 64
    risk = repo.get_risk(db, iid)
    assert (risk.points, risk.tier, risk.action) == (0, "GREEN", "AUTO_RELEASE")
    assert inv["status"] == "AUTO_APPROVED"


def test_oversize_upload_is_rejected_and_nothing_stored(db):
    raw = b"From: a@acme-supply.com\nSubject: x\n\n" + b"y" * 1_048_576
    with pytest.raises(ValueError):
        engine.ingest_upload(raw, conn=db)
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0


def test_unparseable_upload_is_rejected(db):
    with pytest.raises(ValueError):
        engine.ingest_upload(b"\x89PNG\r\n\x1a\n not an email", conn=db)
    with pytest.raises(ValueError):
        engine.ingest_upload(b"Subject: no from header\n\nbody\n", conn=db)
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == 0


def test_html_only_upload_is_stripped_and_scored(db):
    raw = (b"From: ar@heartland-logistics.com\nTo: ap@x\nSubject: Invoice HL-9000\nMIME-Version: 1.0\n"
           b"Content-Type: text/html; charset=utf-8\n\n"
           b"<html><body><h1>Invoice</h1><p>Invoice number: HL-9000</p><p>Amount due: $4,000.00</p>"
           b"<p>Bank: Gateway National Bank<br>Routing number: 044000105<br>Account number: 6620194455</p></body></html>\n")
    iid = engine.ingest_upload(raw, conn=db)
    risk = repo.get_risk(db, iid)
    assert risk.vendor_id == "ven_heartland" and risk.sender_status == "KNOWN"
    assert {f.code for f in risk.flags} == {"BANK_CHANGED"}
    assert risk.action == "CALLBACK"
    assert "<p>" not in repo.get_invoice(db, iid)["body_text"]


def test_multipart_with_attachment_uses_plain_part(db):
    raw = (b"From: billing@prairiecloud.io\nTo: ap@x\nSubject: Invoice PCH-2000\nMIME-Version: 1.0\n"
           b'Content-Type: multipart/mixed; boundary="XX"\n\n--XX\nContent-Type: text/plain\n\n'
           b"Invoice number: PCH-2000\nAmount due: $2,499.00\nBank: Midland Trust Bank\nRouting number: 301112228\n"
           b"Account number: 8800142201\n\n--XX\nContent-Type: application/pdf\n"
           b'Content-Disposition: attachment; filename="invoice.pdf"\n\n%PDF-1.4 binary\n--XX--\n')
    iid = engine.ingest_upload(raw, conn=db)
    risk = repo.get_risk(db, iid)
    assert risk.flags == [] and risk.action == "AUTO_RELEASE"
    assert "%PDF" not in repo.get_invoice(db, iid)["body_text"]
