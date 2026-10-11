"""The callback through the real webhooks (PLAN.md §12.2–§12.6; §17.1 test_voice_flow.py).

Signed requests drive spec 005's pipeline handlers; every §17.1 row plus the analyze fixes
(U1 replays, I1 duplicate status callbacks, E1 retry, R5 one "Answered", R10 exact question).
"""
from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app import ai_mode, config, executors, ledger, pipeline, repo
from app.ids import new_id, now_iso
from app.main import app
from app.state import Status
from app.voice import twiml
from tests.fakes import VERIFIER, ScriptedModel, SlowModel, structured_turn
from tests.helpers import drive_to, make_verification
from tests.twilio_helpers import calling, latest, post

EXPIRED = "This verification line has expired."
NO_SPEECH = {"SpeechResult": "No, we never changed banks", "Confidence": "0.93"}


def _inv(db, iid) -> dict:
    return repo.get_invoice(db, iid)


def _audit(db, iid, event: str | None = None) -> list[dict]:
    q = "SELECT event, actor, data FROM audit_log WHERE subject_id=?" + (" AND event=?" if event else "") + " ORDER BY seq"
    return [{"event": r[0], "actor": r[1], **json.loads(r[2])} for r in db.execute(q, (iid, event) if event else (iid,))]


def _has(xml: str, text: str) -> bool:
    return text in xml.replace("&apos;", "'")


def _answer(client, tok, n=1, **params):
    return post(client, f"/twilio/answer/{tok}?n={n}", params)


@pytest.fixture
def no_grace(monkeypatch):
    monkeypatch.setattr(pipeline, "COMPLETED_GRACE_S", 0)


# ---- PLAN.md §17.1 rows --------------------------------------------------------------

@pytest.mark.parametrize("answer", [NO_SPEECH, {"Digits": "2"}], ids=["spoken", "keypad"])
def test_fraud_no_holds(client, db, twilio_env, answer):
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    assert twilio_env.calls[-1]["to"] == repo.get_vendor(db, "ven_acme")["phone_on_file"]
    assert _has(post(client, f"/twilio/voice/{tok}").text, twiml.q1_text(pipeline.get_call_context(latest(db, iid)["id"])))
    r = _answer(client, tok, **answer)
    assert _has(r.text, "We will not send this payment") and "<Hangup />" in r.text
    inv = _inv(db, iid)
    assert (inv["status"], inv["hold_reason"]) == ("HELD", "DENIED_BY_VENDOR")
    assert latest(db, iid)["final_label"] == "DENIED" and inv["memo"] is not None


def test_heartland_yes_and_matching_last4_releases(client, db, twilio_env):
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    r = _answer(client, tok, Digits="1")
    assert 'numDigits="4"' in r.text and _has(r.text, twiml.ASK_LAST4)
    r = post(client, f"/twilio/last4/{tok}", {"Digits": "4455"})
    assert _has(r.text, twiml.L4_OK)
    inv = _inv(db, iid)
    assert inv["status"] == "RELEASED"
    assert repo.get_payment(db, iid)["account"].endswith("4455")
    assert repo.get_vendor(db, "ven_heartland")["bank_name"] == "Gateway National Bank"


def test_heartland_wrong_last4_holds(client, db, twilio_env):
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    _answer(client, tok, Digits="1")
    assert _has(post(client, f"/twilio/last4/{tok}", {"Digits": "1111"}).text, twiml.L4_BAD)
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "LAST4_MISMATCH")
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0


def test_no_answer_holds(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    assert post(client, f"/twilio/status/{twilio_env.last_token}", {"CallStatus": "no-answer"}).status_code == 204
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "NO_ANSWER")


def test_duplicated_answer_webhook_changes_nothing(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    first = _answer(client, tok, Digits="2").text
    version, changes = _inv(db, iid)["version"], len(_audit(db, iid, "status_changed"))
    assert _answer(client, tok, Digits="2").text == first
    assert _inv(db, iid)["version"] == version and len(_audit(db, iid, "status_changed")) == changes


def test_simulate_supersedes_a_live_verification(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    old_tok, old_ver = twilio_env.last_token, latest(db, iid)["id"]
    pipeline.simulate_answer(iid, "no", None)
    assert repo.get_verification(db, old_ver)["final_label"] == "SUPERSEDED"
    assert twilio_env.cancelled == ["CA_test"]
    version = _inv(db, iid)["version"]
    assert EXPIRED in post(client, f"/twilio/voice/{old_tok}").text
    assert EXPIRED in _answer(client, old_tok, Digits="1").text
    assert post(client, f"/twilio/status/{old_tok}", {"CallStatus": "completed"}).status_code == 204
    assert _inv(db, iid)["version"] == version and _inv(db, iid)["hold_reason"] == "DENIED_BY_VENDOR"


def test_completed_while_verifying_does_not_hold(client, db, twilio_env, no_grace, monkeypatch):
    monkeypatch.setattr(pipeline, "await_verifier", lambda ver_id: None)      # keep it VERIFYING
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    assert 'numDigits="4"' in _answer(client, tok, SpeechResult="Yes we did", Confidence="0.9").text
    assert _has(post(client, f"/twilio/last4/{tok}", {"Digits": "4455"}).text, twiml.L4_OK)
    assert _inv(db, iid)["status"] == "VERIFYING"
    assert post(client, f"/twilio/status/{tok}", {"CallStatus": "completed"}).status_code == 204
    assert _inv(db, iid)["status"] == "VERIFYING"


@pytest.mark.parametrize("before_hangup", ["answered", "awaiting_last4"])
def test_hang_up_before_answering_holds_unclear(client, db, twilio_env, no_grace, before_hangup):
    """US1/AC7: 'completed' while the step is at or before awaiting_last4 → HELD(UNCLEAR_ANSWER)."""
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    post(client, f"/twilio/voice/{tok}")                                      # step answered
    if before_hangup == "awaiting_last4":
        _answer(client, tok, Digits="1")
    assert latest(db, iid)["step"] == before_hangup
    assert post(client, f"/twilio/status/{tok}", {"CallStatus": "completed"}).status_code == 204
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "UNCLEAR_ANSWER")
    assert latest(db, iid)["final_label"] == "UNCLEAR"


def test_spoken_yes_with_ai_off_is_held(client, db, twilio_env):
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    _answer(client, tok, SpeechResult="yes we did", Confidence="0.9")
    assert _has(post(client, f"/twilio/last4/{tok}", {"Digits": "4455"}).text, twiml.L4_OK)   # neutral either way
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "VERIFIER_DISAGREED")
    assert repo.get_vendor(db, "ven_heartland")["bank_name"] == "River City Bank"


# ---- more §12.5 paths ------------------------------------------------------------------

def test_unclear_twice_holds(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    r = _answer(client, tok, n=1, SpeechResult="hmm")
    assert _has(r.text, "Sorry, I didn't catch that.") and f"/twilio/answer/{tok}?n=2" in r.text
    r = _answer(client, tok, n=2, SpeechResult="")
    assert _has(r.text, twiml.UNCLEAR)
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "UNCLEAR_ANSWER")


def test_silent_last4_holds(client, db, twilio_env):
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    _answer(client, tok, Digits="1")
    assert _has(post(client, f"/twilio/last4/{tok}", {"Digits": ""}).text, twiml.UNCLEAR)    # via the redirect
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "UNCLEAR_ANSWER")


def test_other_call_sid_is_not_acted_on(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    r = post(client, f"/twilio/answer/{tok}?n=1", {"CallSid": "CA_someone_else", "Digits": "1"})
    assert EXPIRED in r.text and _inv(db, iid)["status"] == "CALLING"


def test_first_fetch_stores_the_call_sid(client, db, twilio_env):
    iid = calling("02_acme_fraud")
    repo.update_verification(db, latest(db, iid)["id"], call_sid=None)
    assert "<Gather" in post(client, f"/twilio/voice/{twilio_env.last_token}", {"CallSid": "CA_first"}).text
    assert latest(db, iid)["call_sid"] == "CA_first"


@pytest.mark.parametrize(("last4", "replay"), [("4455", twiml.L4_OK), ("1111", twiml.UNCLEAR)])
def test_final_verification_replays_its_script(client, db, twilio_env, last4, replay):
    calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    _answer(client, tok, Digits="1")
    post(client, f"/twilio/last4/{tok}", {"Digits": last4})
    assert _has(_answer(client, tok, Digits="1").text, replay)
    assert _has(post(client, f"/twilio/voice/{tok}").text, replay)


def test_replayed_answer_after_reprompt_is_not_a_second_attempt(client, db, twilio_env):
    """analyze U1: the same ?n=1 webhook twice must not count as the vendor's second answer."""
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    first = _answer(client, tok, n=1, SpeechResult="hmm").text
    assert _answer(client, tok, n=1, SpeechResult="hmm").text == first
    assert latest(db, iid)["attempts"] == 1 and _inv(db, iid)["status"] == "CALLING"
    assert _has(_answer(client, tok, n=2, Digits="2").text, "We will not send this payment")
    assert _inv(db, iid)["hold_reason"] == "DENIED_BY_VENDOR"


def test_replayed_answer_while_awaiting_last4_asks_again(client, db, twilio_env):
    calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    asked = _answer(client, tok, Digits="1").text
    assert _answer(client, tok, Digits="1").text == asked


def test_status_callbacks_are_idempotent(client, db, twilio_env, no_grace, monkeypatch):
    """analyze I1 / SC-004: retries and the voice fetch add no extra audit rows or timeline events."""
    monkeypatch.setattr(pipeline, "await_verifier", lambda ver_id: None)
    iid = calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    for status in ("initiated", "ringing", "ringing"):
        post(client, f"/twilio/status/{tok}", {"CallStatus": status})
    post(client, f"/twilio/voice/{tok}")
    post(client, f"/twilio/status/{tok}", {"CallStatus": "in-progress"})
    labels = [e["label"] for e in latest(db, iid)["events"]]
    assert labels.count("Ringing") == 1 and labels.count("Answered") == 1
    statuses = [a["status"] for a in _audit(db, iid, "call_status")]
    assert statuses == ["ringing", "in-progress"]
    _answer(client, tok, SpeechResult="Yes we did")
    post(client, f"/twilio/last4/{tok}", {"Digits": "4455"})                    # VERIFYING
    post(client, f"/twilio/status/{tok}", {"CallStatus": "completed"})
    post(client, f"/twilio/status/{tok}", {"CallStatus": "completed"})
    assert [a["status"] for a in _audit(db, iid, "call_status")].count("completed") == 1


def test_retry_gets_a_fresh_token(client, db, twilio_env):
    """analyze E1 / US5 AC1."""
    iid = calling("02_acme_fraud")
    old = twilio_env.last_token
    post(client, f"/twilio/status/{old}", {"CallStatus": "no-answer"})
    pipeline.retry_callback(iid)
    new = twilio_env.last_token
    assert new != old and _inv(db, iid)["status"] == "CALLING"
    # the old verification is final (NO_ANSWER), so §12.2 replays UNCLEAR and changes nothing
    version = _inv(db, iid)["version"]
    assert _has(post(client, f"/twilio/voice/{old}").text, twiml.UNCLEAR)
    assert _inv(db, iid)["version"] == version
    assert "Did Acme Supply Co. request this bank change?" in post(client, f"/twilio/voice/{new}").text


def test_change_case_call(client, db, twilio_env):
    case_id, ts = new_id("cc_"), now_iso()
    db.execute("INSERT INTO change_cases (id, idempotency_key, account_ref, requested_change, sender_email, "
               "request_excerpt, signals, callback_target, source_refs, dataset_version, status, created_by, "
               "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (case_id, "k1", json.dumps({"id": "a1", "name": "Acme Holdings", "source_ref": {}}), "billing_contact",
                "x@y.com", "please change", "[]", None, "[]", "public", "OPEN", "devrev", ts, ts))
    invoices = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    pipeline.request_callback(case_id, "change_case")
    assert twilio_env.calls[-1]["to"] == config.S.demo_vendor_phone
    tok = twilio_env.last_token
    xml = post(client, f"/twilio/voice/{tok}").text
    assert _has(xml, "to change the billing contact on their account. Did your organization make this request?")
    assert _has(_answer(client, tok, Digits="2").text, "We will not make this change")
    assert db.execute("SELECT status FROM change_cases WHERE id=?", (case_id,)).fetchone()[0] == "DENIED"
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == invoices
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0


def test_verifier_gets_the_exact_question(client, db, twilio_env, fake_models):
    """research R10: the Verifier sees the Q1 the vendor heard."""
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    ai_mode.set_ai_mode("live", record=False)
    model = ScriptedModel([structured_turn({"label": "DENIED", "rationale": "said no"})])
    fake_models({VERIFIER: lambda: model})
    _answer(client, tok, **NO_SPEECH)
    q1 = twiml.q1_text(pipeline.get_call_context(latest(db, iid)["id"]))
    assert q1 in model.prompt_text() and "No, we never changed banks" in model.prompt_text()


def test_every_webhook_answers_in_under_a_second(client, db, twilio_env, no_grace):
    calling("03_heartland_bank_change")
    tok = twilio_env.last_token
    for path, params in ((f"/twilio/status/{tok}", {"CallStatus": "ringing"}), (f"/twilio/voice/{tok}", {}),
                         (f"/twilio/answer/{tok}?n=1", {"Digits": "1"}), (f"/twilio/last4/{tok}", {"Digits": "4455"}),
                         (f"/twilio/status/{tok}", {"CallStatus": "completed"})):
        t0 = time.perf_counter()
        r = post(client, path, params)
        assert r.status_code in (200, 204) and time.perf_counter() - t0 < 1.0, path


def test_spoken_answer_never_waits_for_the_model(client, db, twilio_env, fake_models):
    """FR-006 / SC-005 (research R12): AI live, real pools, a Verifier that takes 5 s."""
    iid = calling("02_acme_fraud")
    tok = twilio_env.last_token
    ai_mode.set_ai_mode("live", record=False)
    fake_models({VERIFIER: lambda: SlowModel(5.0, [structured_turn({"label": "DENIED", "rationale": "no"})])})
    executors.use_thread_executors()
    try:
        t0 = time.perf_counter()
        r = _answer(client, tok, **NO_SPEECH)
        elapsed = time.perf_counter() - t0
        assert elapsed < 1.0 and _has(r.text, "We will not send this payment")
        assert latest(db, iid)["llm_label"] is None                          # the model has not answered yet
    finally:
        executors.wait_idle(20)


# ---- simulated mode (US3) -------------------------------------------------------------

@pytest.fixture
def simulated(twilio_env, monkeypatch):
    monkeypatch.setenv("VOICE_MODE", "simulated")
    config.reload()
    return twilio_env


def test_simulated_mode_places_no_call(db, simulated):
    iid = calling("02_acme_fraud")
    ver = latest(db, iid)
    assert simulated.calls == [] and ver["source"] == "simulated" and _inv(db, iid)["status"] == "CALLING"
    assert "Simulated line: answer with the demo controls" in [e["label"] for e in ver["events"]]


def test_simulated_answer_through_the_api(db, simulated):
    iid = calling("02_acme_fraud")
    with TestClient(app) as api:
        r = api.post("/api/demo/simulate-answer", json={"subject_id": iid, "answer": "no", "last4": None})
    assert r.status_code == 200
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "DENIED_BY_VENDOR")
    rows = _audit(db, iid)
    start = next(i for i, a in enumerate(rows) if a["event"] == "callback_requested")
    voice_path = [a for a in rows[start:] if a["event"] in ("callback_requested", "answer_received", "status_changed",
                                                              "verification_final", "call_status")]
    assert voice_path and all(a.get("simulated") is True for a in voice_path)
    assert {a["actor"] for a in voice_path if a["event"] in ("answer_received", "verification_final")} == {"demo"}


def test_outside_demo_mode_simulation_is_refused(db, simulated, monkeypatch):
    iid = calling("02_acme_fraud")
    monkeypatch.setenv("DEMO_MODE", "0")
    config.reload()
    with TestClient(app) as api:
        assert api.post("/api/demo/simulate-answer",
                        json={"subject_id": iid, "answer": "no", "last4": None}).status_code == 404
    other = calling("01_acme_normal")
    db.execute("DELETE FROM payments WHERE invoice_id=?", (other,))
    db.execute("UPDATE invoices SET status='SCORED' WHERE id=?", (other,))
    drive_to(db, other, Status.CONFIRMED)
    make_verification(db, other, final_label="CONFIRMED", source="simulated", digits="1", det_label="YES")
    ok, reason = ledger.can_release(other, conn=db)
    assert ok is False and "simulated" in reason
