"""The §7.6 InvoiceDetail shape: exact keys, masking, and the fixtures exporter."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import engine, ledger, repo
from app.state import HoldReason, Status
from tests.helpers import drive_to, make_verification

TOP_KEYS = {
    "id", "status", "hold_reason", "source", "created_at", "invoice_number", "amount_cents", "decided_at",
    "email", "extracted", "vendor", "risk", "destination", "analyst", "verification", "payment", "memo",
    "trace", "audit", "actions", "ai_fallback",
}
EMAIL_KEYS = {"from_name", "from_email", "reply_to", "subject", "received_at", "body_text"}
RISK_KEYS = {"points", "tier", "action", "sender_status", "amount_ratio", "lookalike", "flags", "bank_changed", "policy_version"}
FLAG_KEYS = {"code", "points", "title", "detail", "evidence"}
DEST_KEYS = {"on_file", "requested", "changed"}
ACTION_KEYS = {"can_review", "can_retry_call", "can_simulate", "can_redteam"}
VENDOR_KEYS = {"id", "name", "domains", "phone_masked", "bank_masked", "history", "median_cents"}
VER_KEYS = {"id", "source", "step", "phone_masked", "events", "first_answer", "last4_ok", "final_label", "attempts"}
PAY_KEYS = {"id", "invoice_id", "amount_cents", "bank_name", "routing", "account_masked", "method", "effective_date",
            "released_at", "released_by"}
AUDIT_KEYS = {"seq", "ts", "actor", "event", "summary", "hash_short"}

ACCOUNTS = ["4421984821", "5512003377", "8800142201", "7730019942", "6620194455", "5098812230"]


def _check_shape(d: dict) -> None:
    assert set(d) == TOP_KEYS, set(d) ^ TOP_KEYS
    assert set(d["email"]) == EMAIL_KEYS
    assert set(d["extracted"]) == {"fields", "phone_numbers_in_email", "llm_status"}
    assert set(d["extracted"]["fields"]) == {"vendor_name", "invoice_number", "amount", "due_date", "bank_name",
                                             "routing_number", "account_number"}
    for f in d["extracted"]["fields"].values():
        assert set(f) == {"value", "source", "mismatch"}
    if d["risk"] is not None:
        assert set(d["risk"]) == RISK_KEYS
        for fl in d["risk"]["flags"]:
            assert set(fl) == FLAG_KEYS
    assert set(d["destination"]) == DEST_KEYS
    assert set(d["actions"]) == ACTION_KEYS
    if d["vendor"] is not None:
        assert set(d["vendor"]) == VENDOR_KEYS
        assert len(d["vendor"]["history"]) <= 6
        paid = [h["paid_on"] for h in d["vendor"]["history"]]
        assert paid == sorted(paid)
    if d["verification"] is not None:
        assert set(d["verification"]) == VER_KEYS
    if d["payment"] is not None:
        assert set(d["payment"]) == PAY_KEYS
    for a in d["audit"]:
        assert set(a) == AUDIT_KEYS
    # masking: no full account number anywhere except the raw email body
    body = d["email"]["body_text"]
    scrubbed = json.dumps({**d, "email": {**d["email"], "body_text": ""}})
    for acct in ACCOUNTS:
        assert acct not in scrubbed, acct
    assert isinstance(body, str)


def test_fraud_detail(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    d = repo.invoice_detail(db, iid)
    _check_shape(d)
    assert d["status"] == "CALL_PENDING" and d["amount_cents"] == 4875000 and d["invoice_number"] == "INV-20447"
    assert d["risk"]["lookalike"] == {"sender_domain": "acme-supp1y.com", "known_domain": "acme-supply.com",
                                      "diff": [{"index": 9, "sender": "1", "known": "l"}]}
    assert d["risk"]["amount_ratio"] == 4.06
    assert d["destination"]["on_file"] == {"bank_name": "Plains Federal Bank", "routing": "123456780", "account_masked": "••••4821"}
    assert d["destination"]["requested"] == {"bank_name": "First Coastal Trust", "routing": "061100059", "account_masked": "••••9942"}
    assert d["destination"]["changed"] is True
    assert d["vendor"]["bank_masked"] == "Plains Federal Bank ••••4821" and d["vendor"]["median_cents"] == 1202000
    assert d["vendor"]["history"][-1]["invoice_number"] == "INV-20412"
    assert d["extracted"]["fields"]["account_number"]["value"] == "••••9942"
    assert d["extracted"]["fields"]["routing_number"] == {"value": "061100059", "source": "regex", "mismatch": False}
    assert d["extracted"]["phone_numbers_in_email"] == ["(816) 555-0142"]
    assert d["actions"] == {"can_review": False, "can_retry_call": False, "can_simulate": True, "can_redteam": True}
    assert d["analyst"] == {"status": "pending", "report": None}
    assert d["verification"] is None and d["payment"] is None and d["decided_at"] is None
    assert [a["event"] for a in d["audit"]][:2] == ["invoice_received", "status_changed"]


def test_held_and_paid_details(db):
    iid = engine.ingest_sample("02_acme_fraud", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.DENIED_BY_VENDOR)
    make_verification(db, iid, final_label="DENIED", speech="No, we never changed banks", det_label="NO", confidence=0.93)
    d = repo.invoice_detail(db, iid)
    _check_shape(d)
    assert d["decided_at"] is not None
    assert d["verification"]["final_label"] == "DENIED" and d["verification"]["phone_masked"] == "•••-•••-0199"
    assert d["verification"]["first_answer"]["channel"] == "speech"
    assert d["actions"]["can_retry_call"] is False and d["actions"]["can_simulate"] is False

    iid2 = engine.ingest_sample("01_acme_normal", conn=db)
    d2 = repo.invoice_detail(db, iid2)
    assert d2["actions"]["can_redteam"] is False            # releasable → red team not offered
    assert d2["destination"]["changed"] is False
    assert d2["destination"]["requested"]["routing"] == "123456780"
    ledger.release(iid2, by="policy:auto", conn=db)
    d2 = repo.invoice_detail(db, iid2)
    _check_shape(d2)
    assert d2["payment"]["account_masked"] == "••••4821" and d2["payment"]["method"] == "ACH-CCD"
    assert d2["status"] == "RELEASED" and d2["actions"]["can_redteam"] is True


def test_unknown_vendor_and_review_details(db):
    iid = engine.ingest_sample("05_unknown_vendor", conn=db)
    d = repo.invoice_detail(db, iid)
    _check_shape(d)
    assert d["vendor"] is None and d["destination"]["on_file"] is None
    assert d["destination"]["requested"]["routing"] == "071000014"
    assert d["risk"]["lookalike"] is None and d["risk"]["amount_ratio"] is None
    iid4 = engine.ingest_sample("04_prairie_review", conn=db)
    d4 = repo.invoice_detail(db, iid4)
    assert d4["actions"]["can_review"] is True and d4["risk"]["amount_ratio"] == 2.1


def test_retryable_hold_offers_retry_and_simulate(db):
    iid = engine.ingest_sample("03_heartland_bank_change", conn=db)
    drive_to(db, iid, Status.HELD, HoldReason.NO_ANSWER)
    d = repo.invoice_detail(db, iid)
    assert d["actions"]["can_retry_call"] is True and d["actions"]["can_simulate"] is True


def test_views(db):
    engine.ingest_sample("01_acme_normal", conn=db)
    iid = engine.ingest_sample("05_unknown_vendor", conn=db)
    vendors = repo.vendors_view(db)
    assert [v["id"] for v in vendors] == ["ven_acme", "ven_heartland", "ven_prairie"]
    assert vendors[0]["account_masked"] == "••••4821" and vendors[0]["bank_history"] == []
    pv = repo.payments_view(db)
    assert pv["payments"] == [] and [h["id"] for h in pv["held"]] == [iid]
    stats = repo.stats_view(db)
    assert stats["invoices"] == 2 and stats["held_cents"] == 730000 and stats["released_cents"] == 0
    assert set(stats) == {"released_cents", "held_cents", "invoices", "calls_placed", "median_decision_seconds"}


def test_export_fixtures_writes_all_scenarios(tmp_path):
    from scripts import export_fixtures

    idx = export_fixtures.main(tmp_path)
    assert list(idx) == ["acme_normal", "acme_fraud", "heartland_bank_change", "prairie_review", "unknown_vendor"]
    finals = {s: steps[-1]["status"] for s, steps in idx.items()}
    assert finals == {"acme_normal": "RELEASED", "acme_fraud": "HELD", "heartland_bank_change": "RELEASED",
                      "prairie_review": "RELEASED", "unknown_vendor": "HELD"}
    assert idx["acme_fraud"][-1]["hold_reason"] == "DENIED_BY_VENDOR"
    assert idx["unknown_vendor"][-1]["hold_reason"] == "UNKNOWN_VENDOR"
    assert [s["step"] for s in idx["heartland_bank_change"]] == ["scored", "calling", "confirmed", "paid"]
    for scenario, steps in idx.items():
        for s in steps:
            d = json.loads((tmp_path / s["file"]).read_text())
            _check_shape(d)
    for name in ("index.json", "invoices_list.json", "vendors.json", "payments.json", "stats.json", "health.json", "audit.json"):
        assert (tmp_path / name).exists()
    vendors = json.loads((tmp_path / "vendors.json").read_text())
    heartland = next(v for v in vendors if v["id"] == "ven_heartland")
    assert heartland["bank_masked"] == "Gateway National Bank ••••4455" and len(heartland["bank_history"]) == 1
    payments = json.loads((tmp_path / "payments.json").read_text())
    assert len(payments["payments"]) == 3 and len(payments["held"]) == 2
    audit_fx = json.loads((tmp_path / "audit.json").read_text())
    assert audit_fx["chain_ok"] is True
    # deterministic: a second run is byte-identical
    second = tmp_path / "second"
    export_fixtures.main(second)
    for p in sorted(tmp_path.glob("*/*.json")):
        if p.parts[-2] == "second":
            continue
        rel = Path(p.parts[-2]) / p.parts[-1]
        assert (second / rel).read_bytes() == p.read_bytes(), rel
    assert (second / "stats.json").read_bytes() == (tmp_path / "stats.json").read_bytes()
    assert re.fullmatch(r"inv_fixture\d{2}", idx["acme_normal"][0]["invoice_id"])


def test_cli_smoke(db, capsys):
    from app import cli

    assert cli.main(["score", "02_acme_fraud"]) == 0
    out = capsys.readouterr().out
    assert "160 points, RED, CALLBACK → CALL_PENDING" in out
    assert cli.main(["list"]) == 0
    assert cli.main(["audit-verify"]) == 0
    assert "chain_ok=True" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.main(["nope"])
