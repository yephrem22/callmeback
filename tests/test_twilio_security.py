"""PLAN.md §12.2 on every /twilio/* route (§17.1 test_twilio_security.py): signatures against
PUBLIC_BASE_URL, hashed one-time tokens, expiry, supersede, and tokens kept out of logs."""
from __future__ import annotations

import json
import logging

import pytest

from app import config, repo
from app.voice import security, tokens
from tests.twilio_helpers import AUTH, BASE, calling, latest, post, sign

EXPIRED = "This verification line has expired."


def _rejections(db) -> list[dict]:
    return [json.loads(r[0]) | {"actor": r[1], "subject": r[2]} for r in db.execute(
        "SELECT data, actor, subject_id FROM audit_log WHERE event='webhook_rejected' ORDER BY seq")]


def _snapshot(db, iid):
    inv = repo.get_invoice(db, iid)
    ver = latest(db, iid)
    return inv["status"], inv["version"], ver["step"], ver["final_label"], len(ver["events"])


@pytest.fixture
def fraud(db, twilio_env):
    iid = calling("02_acme_fraud")
    assert repo.get_invoice(db, iid)["status"] == "CALLING"
    return iid, twilio_env.last_token


def test_signed_voice_request_reads_q1(client, fraud):
    _, tok = fraud
    r = post(client, f"/twilio/voice/{tok}")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert "Did Acme Supply Co. request this bank change?" in r.text and "<Gather" in r.text


@pytest.mark.parametrize("tamper", ["param", "auth", "missing", "internal_url"])
def test_bad_signatures_are_403_and_audited(client, db, fraud, tamper):
    iid, tok = fraud
    before = _snapshot(db, iid)
    path = f"/twilio/answer/{tok}?n=1"
    params = {"CallSid": "CA_test", "Digits": "1"}
    if tamper == "param":
        headers = {"X-Twilio-Signature": sign(path, params)}
        r = client.post(path, data={**params, "Digits": "2"}, headers=headers)
    elif tamper == "auth":
        r = post(client, path, {"Digits": "1"}, auth="some-other-token")
    elif tamper == "missing":
        r = post(client, path, {"Digits": "1"}, signed=False)
    else:  # signed for the URL the app sees behind Caddy, not PUBLIC_BASE_URL
        r = post(client, path, {"Digits": "1"}, url=f"http://app:8000{path}")
    assert r.status_code == 403
    assert _snapshot(db, iid) == before
    rej = _rejections(db)
    assert len(rej) == 1 and rej[0]["actor"] == "twilio" and rej[0]["subject"] is None
    assert rej[0]["route"] == "answer" and rej[0]["reason"] == "bad_signature"
    assert tok not in json.dumps(rej) and rej[0]["token_sha8"] == tokens.hash_token(tok)[:8]


def test_no_auth_token_rejects_everything(client, db, fraud, monkeypatch):
    _, tok = fraud
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    config.reload()
    for route in ("voice", "answer", "last4", "status"):
        assert post(client, f"/twilio/{route}/{tok}").status_code == 403
    assert {r["reason"] for r in _rejections(db)} == {"no_auth_token"}


def test_unknown_token_hears_expiry_and_status_is_204(client, db):
    assert EXPIRED in post(client, "/twilio/voice/not-a-token").text
    assert EXPIRED in post(client, "/twilio/answer/not-a-token?n=1", {"Digits": "1"}).text
    assert EXPIRED in post(client, "/twilio/last4/not-a-token", {"Digits": "4455"}).text
    assert post(client, "/twilio/status/not-a-token", {"CallStatus": "ringing"}).status_code == 204


def test_expired_token_changes_nothing(client, db, fraud):
    iid, tok = fraud
    repo.update_verification(db, latest(db, iid)["id"], expires_at="2026-01-01T00:00:00Z")
    before = _snapshot(db, iid)
    assert EXPIRED in post(client, f"/twilio/voice/{tok}").text
    assert EXPIRED in post(client, f"/twilio/answer/{tok}?n=1", {"Digits": "2"}).text
    assert post(client, f"/twilio/status/{tok}", {"CallStatus": "no-answer"}).status_code == 204
    assert _snapshot(db, iid) == before


def test_superseded_token_hears_expiry(client, db, fraud):
    iid, tok = fraud
    repo.update_verification(db, latest(db, iid)["id"], final_label="SUPERSEDED", step="done")
    before = _snapshot(db, iid)
    assert EXPIRED in post(client, f"/twilio/answer/{tok}?n=1", {"Digits": "2"}).text
    assert _snapshot(db, iid) == before


def test_query_string_is_part_of_the_signed_url(client, fraud):
    _, tok = fraud
    path = f"/twilio/answer/{tok}?n=1"
    params = {"CallSid": "CA_test", "Digits": "1"}
    wrong = {"X-Twilio-Signature": sign(f"/twilio/answer/{tok}", params)}   # signed without the query
    assert client.post(path, data=params, headers=wrong).status_code == 403


def test_validate_off_is_honored_only_in_simulated_mode(client, db, fraud, monkeypatch):
    _, tok = fraud
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURE", "0")
    monkeypatch.setenv("DEMO_MODE", "1")
    config.reload()                                     # VOICE_MODE=twilio: the setting is ignored (analyze C1)
    assert post(client, f"/twilio/voice/{tok}", signed=False).status_code == 403
    monkeypatch.setenv("VOICE_MODE", "simulated")
    config.reload()
    assert post(client, f"/twilio/voice/{tok}", signed=False).status_code == 200


def test_tokens_never_reach_the_access_log():
    security.install_access_log_redaction()
    security.install_access_log_redaction()             # idempotent
    logger = logging.getLogger("uvicorn.access")
    record = logger.makeRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
                               ("1.2.3.4:5", "POST", "/twilio/voice/SECRET-TOKEN-123?n=1", "1.1", 200), None)
    for f in logger.filters:
        f.filter(record)
    msg = record.getMessage()
    assert "SECRET-TOKEN-123" not in msg and "/twilio/voice/…" in msg
    assert tokens.hash_token("SECRET-TOKEN-123")[:8] in msg
    assert sum(isinstance(f, security.TokenRedactor) for f in logger.filters) == 1


def test_base_url_is_the_signing_url(fraud, monkeypatch):
    class _Req:
        class url:
            path = "/twilio/answer/abc"
            query = "n=2"
    assert security.signed_url(_Req) == f"{BASE}/twilio/answer/abc?n=2"
    assert AUTH  # the fake account token is configured
