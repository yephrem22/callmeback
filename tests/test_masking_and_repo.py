"""Masking (PLAN.md §6) and repo safety checks."""
from __future__ import annotations

import threading

import pytest

from app import audit, repo
from app.ids import new_id
from app.masking import mask_account, mask_phone, masked


def test_mask_helpers():
    assert mask_account("7730019942") == "••••9942"
    assert mask_account(4421984821) == "••••4821"
    assert mask_phone("+18165550199") == "•••-•••-0199"


def test_masked_dict_rules():
    out = masked({
        "account": "7730019942", "account_number": 4421984821, "phone_on_file": "+18165550199",
        "routing": "061100059", "routing_number": "123456780",
        "evidence": ["wire to acct 4421984821 today", "routing 061100059"],
        "idempotency_key": "12345678901234", "twilio_account_sid": "AC1234567890123456",
        "token_hash": "99999999999999999999", "bank_masked": "Plains ••••4821", "amount_cents": 4875000,
    })
    assert out["account"] == "••••9942"
    assert out["account_number"] == "••••4821"
    assert out["phone_on_file"] == "•••-•••-0199"
    assert out["routing"] == "061100059" and out["routing_number"] == "123456780"
    assert out["evidence"] == ["wire to acct ••••4821 today", "routing 061100059"]
    assert out["idempotency_key"] == "12345678901234"
    assert out["twilio_account_sid"] == "AC1234567890123456"
    assert out["token_hash"] == "99999999999999999999"
    assert out["bank_masked"] == "Plains ••••4821"
    assert out["amount_cents"] == 4875000


def test_audit_data_is_masked_and_actors_validated(db):
    audit.append("inv_x", "policy", "risk_scored", {"account": "7730019942", "note": "acct 7730019942"}, conn=db)
    import json
    raw = db.execute("SELECT data FROM audit_log WHERE subject_id='inv_x'").fetchone()[0]
    assert "7730019942" not in raw
    data = json.loads(raw)
    assert data == {"account": "••••9942", "note": "acct ••••9942"}
    with pytest.raises(ValueError):
        audit.append("inv_x", "nobody", "risk_scored", {}, conn=db)
    with pytest.raises(ValueError):
        audit.append("inv_x", "policy", "not_an_event", {}, conn=db)


def test_audit_append_is_serialised_across_threads(db):
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(5):
                audit.append("inv_t", "system", "call_status", {"n": 1})
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    seqs = [r[0] for r in db.execute("SELECT seq FROM audit_log ORDER BY seq").fetchall()]
    assert seqs == list(range(1, 41))


def test_audit_verify_fails_closed_until_chain_exists():
    assert audit.verify() == (False, None)


def test_repo_rejects_unknown_columns(db):
    with pytest.raises(ValueError):
        repo.insert_invoice(db, id=new_id("inv_"), source="sample", raw_sha256="x", body_text="b",
                            **{'status="RELEASED" WHERE 1=1; --': "x"})
    iid = repo.insert_invoice(db, id=new_id("inv_"), source="sample", raw_sha256="x", body_text="b")
    with pytest.raises(ValueError):
        repo.update_invoice(db, iid, nonexistent=1)


def test_list_invoices_uses_join_and_newest_first(db):
    a = repo.insert_invoice(db, id="inv_a", source="sample", raw_sha256="x", body_text="b",
                            vendor_id="ven_acme", created_at="2026-10-10T10:00:00Z")
    b = repo.insert_invoice(db, id="inv_b", source="upload", raw_sha256="y", body_text="b",
                            from_name="Someone", created_at="2026-10-10T11:00:00Z")
    rows = repo.list_invoices(db)
    assert [r["id"] for r in rows] == [b, a]
    assert rows[1]["vendor_name"] == "Acme Supply Co."
    assert rows[0]["vendor_name"] == "Someone"
