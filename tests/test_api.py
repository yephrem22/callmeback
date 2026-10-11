"""The §7.6 HTTP API (spec 005 US4, FR-018..FR-021): one test per row, masking, 409 rules, demo routes."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import ai_mode, config, ledger
from app.ids import new_id, now_iso
from app.main import app
from tests.test_invoice_detail_shape import ACCOUNTS, TOP_KEYS

LIST_KEYS = {"id", "created_at", "vendor_name", "amount_display", "tier", "points", "status", "hold_reason", "source"}
SAMPLES = ["01_acme_normal", "02_acme_fraud", "03_heartland_bank_change", "04_prairie_review", "05_unknown_vendor"]


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        yield c


def _masked_ok(text: str) -> None:
    for acct in ACCOUNTS:
        assert acct not in text, f"unmasked account {acct}"
    assert "8165550199" not in text and "816-555-0199" not in text     # vendor phone on file


def _get(client, path, **kw):
    r = client.get(path, **kw)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    data = r.json()
    # same rule as spec 003's shape test: the raw email body is shown as received; nothing else is unmasked
    scrubbed = {**data, "email": {**data["email"], "body_text": ""}} if isinstance(data, dict) and "email" in data else data
    _masked_ok(json.dumps(scrubbed, ensure_ascii=False))
    return data


def _submit(client, name) -> str:
    r = client.post("/api/invoices/from-sample", json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _add_case(db) -> str:
    case_id, ts = new_id("cc_"), now_iso()
    db.execute("INSERT INTO change_cases (id, idempotency_key, account_ref, requested_change, sender_email, "
               "request_excerpt, signals, callback_target, source_refs, dataset_version, status, created_by, "
               "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (case_id, "k-" + case_id, json.dumps({"id": "a1", "name": "Acme", "source_ref": {}}), "billing_contact",
                "x@y.com", "please change", "[]", None, "[]", "public", "OPEN", "devrev", ts, ts))
    return case_id


def test_healthz_and_health(client):
    assert client.get("/healthz").json() == {"ok": True}
    h = _get(client, "/api/health")
    assert set(h) == {"db", "model", "twilio", "storage", "demo_mode", "ai_mode", "deploy_label"}
    assert set(h["model"]) == {"ok", "latency_ms", "checked_at", "provider"} and h["model"]["provider"] == "akamai"
    assert h["db"] is True and h["model"]["ok"] is False and h["ai_mode"] == "off"
    assert set(h["twilio"]) == {"configured"} and set(h["storage"]) == {"ok"} and h["demo_mode"] is True


def test_samples(client):
    s = _get(client, "/api/samples")
    assert [x["name"] for x in s] == SAMPLES and all(set(x) == {"name", "title", "description"} for x in s)


def test_from_sample_unknown_is_404(client):
    assert client.post("/api/invoices/from-sample", json={"name": "nope"}).status_code == 404


def test_upload(client):
    raw = (b'From: "Acme Supply Co. Billing" <billing@acme-supply.com>\nSubject: Invoice INV-20450\n'
           b"Date: Sat, 10 Oct 2026 09:00:00 -0500\n\nInvoice number: INV-20450\nAmount due: $11,900.00\n"
           b"Bank: Plains Federal Bank\nRouting number: 123456780\nAccount number: 4421984821\n")
    r = client.post("/api/invoices/upload", files={"file": ("x.eml", raw, "message/rfc822")})
    assert r.status_code == 200 and r.json()["id"].startswith("inv_")
    big = b"From: a@acme-supply.com\nSubject: x\n\n" + b"y" * 1_048_576
    assert client.post("/api/invoices/upload", files={"file": ("big.eml", big, "message/rfc822")}).status_code == 400
    assert client.post("/api/invoices/upload", files={"file": ("x.eml", b"\x00\x01\x02", "message/rfc822")}).status_code == 400
    assert client.post("/api/invoices/upload", files={"file": ("x.pdf", raw, "application/pdf")}).status_code == 400


def test_list_and_detail(client):
    a, b = _submit(client, "01_acme_normal"), _submit(client, "02_acme_fraud")
    rows = _get(client, "/api/invoices")
    assert [r["id"] for r in rows] == [b, a] and all(set(r) == LIST_KEYS for r in rows)
    d = _get(client, f"/api/invoices/{b}")
    assert set(d) == TOP_KEYS
    assert d["destination"]["requested"]["routing"] == "061100059"           # routing shown in full
    assert d["destination"]["requested"]["account_masked"] == "••••9942"
    assert client.get("/api/invoices/inv_nope").status_code == 404


def test_review_409_unless_needs_review_and_approve_pays(client):
    normal, prairie = _submit(client, "01_acme_normal"), _submit(client, "04_prairie_review")
    assert client.post(f"/api/invoices/{normal}/review", json={"decision": "approve", "note": ""}).status_code == 409
    assert client.post(f"/api/invoices/{prairie}/review", json={"decision": "maybe"}).status_code in (400, 422)
    r = client.post(f"/api/invoices/{prairie}/review", json={"decision": "approve", "note": "renewal"})
    assert r.status_code == 200
    assert _get(client, f"/api/invoices/{prairie}")["status"] == "RELEASED"


def test_review_reject_holds_and_writes_a_memo(client):
    prairie = _submit(client, "04_prairie_review")
    assert client.post(f"/api/invoices/{prairie}/review", json={"decision": "reject", "note": "not ours"}).status_code == 200
    d = _get(client, f"/api/invoices/{prairie}")
    assert (d["status"], d["hold_reason"]) == ("HELD", "REVIEW_REJECTED")
    assert d["memo"] is not None and d["payment"] is None                 # FR-006: memo on every HELD entry


def test_retry_callback_409_unless_retryable(client):
    fraud = _submit(client, "02_acme_fraud")
    assert client.post(f"/api/invoices/{fraud}/retry-callback").status_code == 409     # CALLING
    client.post("/api/demo/simulate-answer", json={"subject_id": fraud, "answer": "no", "last4": None})
    assert client.post(f"/api/invoices/{fraud}/retry-callback").status_code == 409     # DENIED is final


def test_redteam(client, db):
    fraud = _submit(client, "02_acme_fraud")
    client.post("/api/demo/simulate-answer", json={"subject_id": fraud, "answer": "no", "last4": None})
    r = client.post(f"/api/invoices/{fraud}/redteam")
    assert r.status_code == 200
    out = r.json()
    assert set(out) == {"blocked", "layer", "reason", "run_id"} and out["blocked"] is True
    prairie = _submit(client, "04_prairie_review")
    ledger.record_review(prairie, "approve", "ok", conn=db)                  # REVIEW_APPROVED: releasable now
    assert client.post(f"/api/invoices/{prairie}/redteam").status_code == 409
    assert db.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?", (fraud,)).fetchone()[0] == 0


def test_audit(client):
    iid = _submit(client, "01_acme_normal")
    a = _get(client, "/api/audit")
    assert set(a) == {"entries", "chain_ok", "broken_at"} and a["chain_ok"] is True and a["broken_at"] is None
    sub = _get(client, "/api/audit", params={"subject_id": iid})["entries"]
    assert sub and all(e["subject_id"] == iid for e in sub)
    assert {"seq", "ts", "actor", "event", "summary", "hash_short"} <= set(sub[0])


def test_payments_stats_vendors(client):
    _submit(client, "01_acme_normal")
    p = _get(client, "/api/payments")
    assert set(p) == {"payments", "held"} and len(p["payments"]) == 1
    s = _get(client, "/api/stats")
    assert set(s) == {"released_cents", "held_cents", "invoices", "calls_placed", "median_decision_seconds"}
    assert s["invoices"] == 1 and s["released_cents"] > 0
    v = _get(client, "/api/vendors")
    assert len(v) >= 3 and all("bank_history" in x for x in v)


def test_change_cases(client, db):
    case_id = _add_case(db)
    rows = _get(client, "/api/change-cases")
    assert [r["id"] for r in rows] == [case_id]
    d = _get(client, f"/api/change-cases/{case_id}")
    assert d["id"] == case_id and d["status"] == "OPEN" and d["account_ref"]["name"] == "Acme"
    assert "verification" in d
    assert client.get("/api/change-cases/cc_nope").status_code == 404


def _heartland(client) -> dict:
    return next(v for v in _get(client, "/api/vendors") if v["id"] == "ven_heartland")


def test_demo_reset(client, db):
    case_id = _add_case(db)
    heart = _submit(client, "03_heartland_bank_change")
    client.post("/api/demo/simulate-answer", json={"subject_id": heart, "answer": "yes", "last4": "4455"})
    assert _heartland(client)["bank_masked"].startswith("Gateway National Bank")
    ai_mode.set_ai_mode("live", record=False)
    assert client.post("/api/demo/reset", json={}).status_code == 200
    assert ai_mode.effective_ai_mode() == config.S.ai_mode                  # the AI override is cleared too
    assert _get(client, "/api/invoices") == []
    assert _heartland(client)["bank_masked"].startswith("River City Bank")
    audit = _get(client, "/api/audit")
    assert audit["entries"][0]["event"] == "demo_reset" and audit["chain_ok"] is True
    assert [r["id"] for r in _get(client, "/api/change-cases")] == [case_id]   # kept
    client.post("/api/demo/reset", json={"include_change_cases": True})
    assert _get(client, "/api/change-cases") == []


def test_simulate_answer(client):
    normal = _submit(client, "01_acme_normal")
    bad = client.post("/api/demo/simulate-answer", json={"subject_id": normal, "answer": "yes", "last4": None})
    assert bad.status_code == 409
    assert client.post("/api/demo/simulate-answer",
                       json={"subject_id": "inv_nope", "answer": "yes", "last4": None}).status_code == 404
    fraud = _submit(client, "02_acme_fraud")
    r = client.post("/api/demo/simulate-answer", json={"subject_id": fraud, "answer": "no", "last4": None})
    assert r.status_code == 200
    d = _get(client, f"/api/invoices/{fraud}")
    assert (d["status"], d["hold_reason"]) == ("HELD", "DENIED_BY_VENDOR")


def test_ai_mode(client):
    assert client.post("/api/demo/ai-mode", json={"mode": "sideways"}).status_code in (400, 422)
    r = client.post("/api/demo/ai-mode", json={"mode": "live"})
    assert r.status_code == 200 and r.json() == {"mode": "live"}
    assert _get(client, "/api/health")["ai_mode"] == "live"
    events = [e["event"] for e in _get(client, "/api/audit")["entries"]]
    assert "ai_mode_changed" in events
    client.post("/api/demo/ai-mode", json={"mode": "off"})
    assert _get(client, "/api/health")["ai_mode"] == "off"


def test_demo_routes_are_404_outside_demo_mode(demo_mode_off):
    with TestClient(app) as client:
        assert client.post("/api/demo/reset", json={}).status_code == 404
        assert client.post("/api/demo/simulate-answer",
                           json={"subject_id": "inv_x", "answer": "no", "last4": None}).status_code == 404
        assert client.post("/api/demo/ai-mode", json={"mode": "live"}).status_code == 404
        assert client.get("/api/health").json()["demo_mode"] is False


def test_five_sample_story_via_the_api(client):
    ids = {n: _submit(client, n) for n in SAMPLES}
    client.post("/api/demo/simulate-answer", json={"subject_id": ids["02_acme_fraud"], "answer": "no", "last4": None})
    client.post("/api/demo/simulate-answer",
                json={"subject_id": ids["03_heartland_bank_change"], "answer": "yes", "last4": "4455"})
    client.post(f"/api/invoices/{ids['04_prairie_review']}/review", json={"decision": "approve", "note": "renewal"})
    statuses = {n: _get(client, f"/api/invoices/{i}")["status"] for n, i in ids.items()}
    assert statuses == {"01_acme_normal": "RELEASED", "02_acme_fraud": "HELD", "03_heartland_bank_change": "RELEASED",
                        "04_prairie_review": "RELEASED", "05_unknown_vendor": "HELD"}
    assert len(_get(client, "/api/payments")["payments"]) == 3
    assert _get(client, "/api/audit")["chain_ok"] is True
    for i in ids.values():
        assert set(_get(client, f"/api/invoices/{i}")) == TOP_KEYS
