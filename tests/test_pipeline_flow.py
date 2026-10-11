"""The demo story through the pipeline (PLAN.md §8.4, §12.5, §12.6; spec US1, US3, FR-015..FR-017)."""
from __future__ import annotations

import json
import re

import pytest

from app import ai_mode, audit, config, engine, ledger, pipeline, repo, voice_port
from app.ids import new_id, now_iso
from tests.fakes import ANALYST, INTAKE, PAYMENTS, VERIFIER, ScriptedModel, structured_turn, text_turn, tool_turn

NULL_EXTRACTION = {"vendor_name": None, "invoice_number": None, "amount": None, "due_date": None, "bank_name": None,
                   "routing_number": None, "account_number": None}
REPORT = {"headline": "h", "explanation": "e", "cited_flags": [], "recommended_next_step": "n"}


def _submit(name: str) -> str:
    return pipeline.submit_invoice(engine.load_sample(name), source="sample", sample_name=name)


def _inv(db, iid):
    return repo.get_invoice(db, iid)


def _ver(db, iid):
    return repo.latest_verification(db, iid)


@pytest.fixture(params=["ai_off", "fakes"])
def mode(request, fake_models):
    if request.param == "fakes":
        ai_mode.set_ai_mode("live", record=False)
        fake_models({
            INTAKE: lambda: ScriptedModel([structured_turn(NULL_EXTRACTION)]),
            ANALYST: lambda: ScriptedModel([structured_turn(REPORT)]),
            VERIFIER: lambda: ScriptedModel([structured_turn({"label": "CONFIRMED", "rationale": "yes"})]),
            # the Payments agent always tries to release; the guard decides
            PAYMENTS: lambda: ScriptedModel([tool_turn("get_case_summary"), tool_turn("release_payment"),
                                             text_turn("Done. Logged the outcome.")]),
        })
    yield request.param
    ai_mode.reset_override()


def test_the_five_samples_reach_their_final_states(db, mode):
    ids = {n: _submit(n) for n in ("01_acme_normal", "02_acme_fraud", "03_heartland_bank_change",
                                   "04_prairie_review", "05_unknown_vendor")}
    assert _inv(db, ids["02_acme_fraud"])["status"] == "CALLING"            # simulated line, no Twilio
    pipeline.simulate_answer(ids["02_acme_fraud"], "no", None)
    pipeline.simulate_answer(ids["03_heartland_bank_change"], "yes", "4455")
    ledger.record_review(ids["04_prairie_review"], "approve", "renewal", conn=db)
    pipeline.run_payments_agent(ids["04_prairie_review"])

    final = {n: (_inv(db, i)["status"], _inv(db, i)["hold_reason"]) for n, i in ids.items()}
    assert final == {
        "01_acme_normal": ("RELEASED", None),
        "02_acme_fraud": ("HELD", "DENIED_BY_VENDOR"),
        "03_heartland_bank_change": ("RELEASED", None),
        "04_prairie_review": ("RELEASED", None),
        "05_unknown_vendor": ("HELD", "UNKNOWN_VENDOR"),
    }
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 3
    heart = repo.get_payment(db, ids["03_heartland_bank_change"])
    assert heart["account"].endswith("4455")
    assert repo.get_vendor(db, "ven_heartland")["bank_name"] == "Gateway National Bank"
    assert audit.verify(db) == (True, None)
    for iid in ids.values():
        inv = _inv(db, iid)
        assert inv["memo"] is not None or inv["status"] == "NEEDS_REVIEW"
        assert inv["analyst"]["status"] in ("done", "fallback")
    if mode == "ai_off":
        assert _inv(db, ids["02_acme_fraud"])["analyst"]["status"] == "fallback"
    # simulated answers are marked in the audit data
    rows = [json.loads(r[0]) for r in db.execute(
        "SELECT data FROM audit_log WHERE subject_id=? AND event IN ('answer_received','verification_final')",
        (ids["02_acme_fraud"],)).fetchall()]
    assert rows and all(r.get("simulated") is True for r in rows)


def test_duplicate_answer_is_a_noop(db):
    iid = _submit("02_acme_fraud")
    ver = _ver(db, iid)["id"]
    assert pipeline.on_first_answer(ver, "2", None, None) == "DENIED"
    version = _inv(db, iid)["version"]
    assert pipeline.on_first_answer(ver, "2", None, None) == "DENIED"
    assert _inv(db, iid)["version"] == version


def test_simulate_supersedes_an_active_real_call(db, monkeypatch):
    cancelled: list[str] = []
    monkeypatch.setattr(voice_port, "cancel_call", cancelled.append)
    iid = _submit("02_acme_fraud")                                         # CALLING on a simulated line
    old = _ver(db, iid)["id"]
    repo.update_verification(db, old, source="twilio", call_sid="CA_old")   # pretend it is a live Twilio call
    pipeline.simulate_answer(iid, "no", None)
    assert repo.get_verification(db, old)["final_label"] == "SUPERSEDED" and cancelled == ["CA_old"]
    assert _inv(db, iid)["hold_reason"] == "DENIED_BY_VENDOR"
    version = _inv(db, iid)["version"]
    pipeline.on_first_answer(old, "1", None, None)                          # late webhook on the old call
    pipeline.on_call_status(old, "completed")
    assert _inv(db, iid)["version"] == version


def test_call_failure_holds_and_retry_works(db, monkeypatch):
    monkeypatch.setenv("VOICE_MODE", "twilio")
    config.reload()
    iid = _submit("02_acme_fraud")                                         # the pre-006 stub cannot place calls
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "CALL_FAILED")
    monkeypatch.setenv("VOICE_MODE", "simulated")
    config.reload()
    pipeline.retry_callback(iid)
    assert _inv(db, iid)["status"] == "CALLING"


def test_no_answer_holds(db):
    iid = _submit("02_acme_fraud")
    pipeline.on_call_status(_ver(db, iid)["id"], "no-answer")
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "NO_ANSWER")
    assert ledger.retry_callback_allowed(iid, conn=db)


def test_completed_while_verifying_does_not_hold(db, monkeypatch):
    monkeypatch.setattr(pipeline, "COMPLETED_GRACE_S", 0)
    monkeypatch.setattr(voice_port, "classify_answer", _classify_12_4)
    monkeypatch.setattr(pipeline, "await_verifier", lambda ver_id: None)    # keep it VERIFYING for this check
    iid = _submit("03_heartland_bank_change")
    ver = _ver(db, iid)["id"]
    assert pipeline.on_first_answer(ver, None, "yes we did", 0.9) == "ASK_LAST4"
    assert pipeline.on_last4(ver, "4455") == "CONFIRMED"
    assert _inv(db, iid)["status"] == "VERIFYING"
    pipeline.on_call_status(ver, "completed")
    assert _inv(db, iid)["status"] == "VERIFYING"


def _classify_12_4(digits, speech):
    """PLAN.md §12.4 rules, used until spec 006 ships the real classifier (analyze I1)."""
    if digits:
        return {"1": "YES", "2": "NO"}.get(digits, "UNCLEAR")
    s = " ".join((speech or "").lower().split())
    no = re.search(r"\bno\b|\bnope\b|\bnot\b|\bnever\b|\bdidn'?t\b|\bdon'?t\b|\bwrong\b|\bincorrect\b", s)
    yes = re.search(r"\byes\b|\byeah\b|\byep\b|\bcorrect\b|\bwe did\b|\bconfirm(ed)?\b", s)
    return "UNCLEAR" if bool(no) == bool(yes) else ("NO" if no else "YES")


def test_spoken_yes_with_ai_off_is_disagreed_but_keypad_confirms(db, monkeypatch):
    monkeypatch.setattr(voice_port, "classify_answer", _classify_12_4)
    spoken = _submit("03_heartland_bank_change")
    v = _ver(db, spoken)["id"]
    assert pipeline.on_first_answer(v, None, "Yes we did", 0.92) == "ASK_LAST4"
    pipeline.on_last4(v, "4455")
    assert (_inv(db, spoken)["status"], _inv(db, spoken)["hold_reason"]) == ("HELD", "VERIFIER_DISAGREED")
    assert repo.get_verification(db, v)["llm_label"] == "UNCLEAR"
    assert repo.get_vendor(db, "ven_heartland")["bank_name"] == "River City Bank"   # not updated

    seed_reset(db)
    keyed = _submit("03_heartland_bank_change")
    v2 = _ver(db, keyed)["id"]
    assert pipeline.on_first_answer(v2, "1", None, None) == "ASK_LAST4"
    assert pipeline.on_last4(v2, "4455") == "CONFIRMED"
    assert _inv(db, keyed)["status"] == "RELEASED"


def seed_reset(db):
    from app import seed
    seed.reset_demo_data(db)


def test_wrong_last_four_holds(db):
    iid = _submit("03_heartland_bank_change")
    v = _ver(db, iid)["id"]
    pipeline.on_first_answer(v, "1", None, None)
    assert pipeline.on_last4(v, "1111") == "MISMATCH"
    assert (_inv(db, iid)["status"], _inv(db, iid)["hold_reason"]) == ("HELD", "LAST4_MISMATCH")


def test_change_case_verification_only_sets_the_case_status(db):
    case_id = new_id("cc_")
    ts = now_iso()
    db.execute("INSERT INTO change_cases (id, idempotency_key, account_ref, requested_change, sender_email, "
               "request_excerpt, signals, callback_target, source_refs, dataset_version, status, created_by, "
               "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (case_id, "k1", json.dumps({"id": "a1", "name": "Acme", "source_ref": {}}), "billing_contact",
                "x@y.com", "please change", "[]", None, "[]", "public", "OPEN", "devrev", ts, ts))
    invoices_before = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    ver = pipeline.request_callback(case_id, "change_case")
    assert db.execute("SELECT status FROM change_cases WHERE id=?", (case_id,)).fetchone()[0] == "CALLING"
    assert repo.get_verification(db, ver)["phone_called"] == config.S.demo_vendor_phone
    pipeline.on_first_answer(ver, "2", None, None)
    assert db.execute("SELECT status FROM change_cases WHERE id=?", (case_id,)).fetchone()[0] == "DENIED"
    assert db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] == invoices_before
    assert db.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0


def test_simulate_is_refused_outside_demo_mode_and_in_the_wrong_state(db, monkeypatch):
    iid = _submit("01_acme_normal")                                          # RELEASED: nothing to simulate
    with pytest.raises(pipeline.SimulateNotAllowed):
        pipeline.simulate_answer(iid, "yes", None)
    fraud = _submit("02_acme_fraud")
    monkeypatch.setenv("DEMO_MODE", "0")
    config.reload()
    with pytest.raises(pipeline.SimulateNotAllowed):
        pipeline.simulate_answer(fraud, "no", None)
