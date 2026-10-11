"""Orchestration (PLAN.md §5, §7.5, §9.4, §12.5, §12.6).

Every invoice: RECEIVED → EXTRACTED → SCORED → routed, as a JOBS task. The fast path scores from the
deterministic extraction so a RED invoice's call is requested before any model answers; the Intake
agent then only fills in the extraction chips. The §7.5 voice entry points implement the §12.5
decision logic; webhooks call them from spec 006's routes, the demo controls through simulate_answer.

Only `app/executors.py` creates threads; this module re-exports its pools (analyze A1).
"""
from __future__ import annotations

import hmac
import logging
import time
from datetime import UTC, datetime
from typing import Literal

from app import audit, config, db, ledger, repo, verifications, voice_port
from app.agents import analyst as analyst_agent
from app.agents import intake_agent, payments, verifier
from app.agents.fallbacks import analyst_fallback, analyst_record, verifier_fallback
from app.agents.runner import run_agent, start_agent
from app.engine import score_invoice
from app.executors import AGENTS, JOBS, use_inline_executors, use_thread_executors  # noqa: F401  (re-export)
from app.ids import new_id, now_iso
from app.intake import eml, merge, regex_extract
from app.models import CallContext, InvoiceExtraction, RiskResult, VerifierLabel
from app.policy import engine as policy
from app.state import RETRYABLE, HoldReason, IllegalTransition, Status, transition
from app.voice import twiml

log = logging.getLogger("pipeline")

COMPLETED_GRACE_S = 3.0      # Twilio can post the answer and the hang-up almost together (§12.5)
VERIFIER_POLL_S = 0.5
_poll_sleep = time.sleep

STEP_ORDER = ["created", "placed", "ringing", "answered", "asked", "awaiting_last4", "verifying", "done"]
INVOICE_OUTCOME = {
    "DENIED": (Status.HELD, HoldReason.DENIED_BY_VENDOR),
    "CONFIRMED": (Status.CONFIRMED, None),
    "UNCLEAR": (Status.HELD, HoldReason.UNCLEAR_ANSWER),
    "LAST4_MISMATCH": (Status.HELD, HoldReason.LAST4_MISMATCH),
    "NO_ANSWER": (Status.HELD, HoldReason.NO_ANSWER),
    "VERIFIER_DISAGREED": (Status.HELD, HoldReason.VERIFIER_DISAGREED),
}
CASE_OUTCOME = {"DENIED": "DENIED", "CONFIRMED": "CONFIRMED", "UNCLEAR": "UNCLEAR", "LAST4_MISMATCH": "UNCLEAR",
                "NO_ANSWER": "NO_ANSWER", "VERIFIER_DISAGREED": "UNCLEAR"}


class SimulateNotAllowed(Exception):
    """simulate-answer outside DEMO_MODE or in a state that has nothing to answer (HTTP 409/404)."""


# =====================================================================================
# Ingest and scoring (PLAN.md §9.4)
# =====================================================================================

def submit_invoice(raw: bytes, *, source: Literal["sample", "upload"], sample_name: str | None) -> str:
    """Parse and store RECEIVED, queue the pipeline job, return the id at once. ValueError → HTTP 400."""
    parsed = eml.parse(raw)
    c = db.connect()
    try:
        invoice_id = new_id("inv_")
        with db.tx(c):
            repo.insert_invoice(
                c, id=invoice_id, source=source, sample_name=sample_name, raw_sha256=parsed.raw_sha256,
                from_name=parsed.from_name, from_email=parsed.from_email, from_domain=parsed.from_domain,
                reply_to=parsed.reply_to or None, reply_to_domain=parsed.reply_to_domain or None,
                subject=parsed.subject, received_at=parsed.received_at, body_text=parsed.body_text,
                status=Status.RECEIVED.value, analyst={"status": "pending", "report": None},
            )
            audit.append(invoice_id, "system", "invoice_received",
                         {"source": source, "sample_name": sample_name, "from_email": parsed.from_email,
                          "subject": parsed.subject, "sha256": parsed.raw_sha256}, conn=c)
    finally:
        c.close()
    JOBS.submit(_pipeline_job, invoice_id, parsed)
    return invoice_id


def _pipeline_job(invoice_id: str, parsed: eml.ParsedEmail) -> None:
    try:
        rx = regex_extract.extract(parsed.body_text)
        c = db.connect()
        try:
            res = policy.resolve_vendor(c, parsed.from_domain, None)        # §10.1 steps 1–2 only
            fast = bool(rx.routing and rx.account and rx.amount) and res.sender_status in ("KNOWN", "LOOKALIKE")
            if fast:
                risk = score_invoice(invoice_id, parsed, c, llm=None, llm_status="pending")
            else:
                llm, outcome = run_agent("intake", invoice_id,
                                         lambda ctx: intake_agent.run_intake(ctx, invoice_id, parsed),
                                         config.S.timeout_intake_s, lambda: None)
                risk = score_invoice(invoice_id, parsed, c, llm=llm,
                                     llm_status="ok" if (llm is not None and outcome == "result") else "fallback")
        finally:
            c.close()
        _after_scoring(invoice_id, risk)
        if fast:
            start_agent("intake", invoice_id, lambda ctx: intake_agent.run_intake(ctx, invoice_id, parsed),
                        config.S.timeout_intake_s, lambda: None,
                        on_done=lambda llm, outcome: _merge_chips(invoice_id, parsed, rx, llm, outcome))
    except Exception:
        log.exception("pipeline job failed for %s", invoice_id)
        try:
            transition(invoice_id, Status.FAILED, actor="system", detail={"reason": "pipeline error"})
        except IllegalTransition:
            pass


def _after_scoring(invoice_id: str, risk: RiskResult) -> None:
    """Route follow-ups first (the phone never waits), then the Analyst in the background."""
    c = db.connect()
    try:
        status = repo.get_invoice(c, invoice_id)["status"]
    finally:
        c.close()
    if status == Status.CALL_PENDING:
        request_callback(invoice_id, "invoice")
    elif status in (Status.AUTO_APPROVED, Status.HELD):
        run_payments_agent(invoice_id)
    start_agent("analyst", invoice_id, lambda ctx: analyst_agent.run_analyst(ctx, invoice_id),
                config.S.timeout_analyst_s, lambda: analyst_fallback(risk),
                on_done=lambda report, outcome: _store_analyst(invoice_id, report, outcome))


def _store_analyst(invoice_id: str, report, outcome: str) -> None:
    status = "done" if outcome == "result" else "fallback"
    c = db.connect()
    try:
        repo.update_invoice(c, invoice_id, analyst=analyst_record(report, status))
        audit.append(invoice_id, "agent:analyst", "analyst_report",
                     {"status": status, "headline": report.headline if report else None,
                      "cited_flags": report.cited_flags if report else []}, conn=c)
    finally:
        c.close()


def _merge_chips(invoice_id: str, parsed: eml.ParsedEmail, rx, llm: InvoiceExtraction | None, outcome: str) -> None:
    """Fast path: merge the late Intake result for display. Never re-scores (§9.4)."""
    status = "ok" if (llm is not None and outcome == "result") else "fallback"
    merged = merge.merge(rx, llm if status == "ok" else None, parsed.body_text, parsed.from_name, llm_status=status)
    c = db.connect()
    try:
        with db.tx(c):
            inv = repo.get_invoice(c, invoice_id)
            repo.update_invoice(c, invoice_id, extraction=merged.model_dump())
            audit.append(invoice_id, "agent:intake", "extraction_done", {"llm_status": status}, conn=c)
            risk = inv.get("risk") or {}
            codes = {f["code"] for f in risk.get("flags", [])}
            if status == "ok" and merge.has_mismatch(merged, rx) and "EXTRACTION_MISMATCH" not in codes:
                flag = policy._flag("EXTRACTION_MISMATCH",                     # 0 points; tier/action unchanged
                                    "The AI read a field differently from the text; the text value was used")
                risk["flags"] = [*risk.get("flags", []), flag.model_dump()]
                repo.update_invoice(c, invoice_id, risk=risk)
                audit.append(invoice_id, "agent:intake", "extraction_mismatch",
                             {"fields": [k for k in ("invoice_number", "amount", "routing_number", "account_number")
                                         if getattr(merged, k).mismatch]}, conn=c)
    finally:
        c.close()


# =====================================================================================
# Payments agent (PLAN.md §11.4)
# =====================================================================================

def run_payments_agent(invoice_id: str) -> None:
    """On entering AUTO_APPROVED, REVIEW_APPROVED, CONFIRMED or HELD (memo only for HELD)."""
    JOBS.submit(_payments_job, invoice_id)


def _payments_job(invoice_id: str) -> None:
    try:
        payments.process_payments(invoice_id)
    except Exception:
        log.exception("payments job failed for %s", invoice_id)


# =====================================================================================
# Callback verification (PLAN.md §7.5, §12.5, §12.6)
# =====================================================================================

def _active_verifications(c, subject_id: str) -> list[dict]:
    return [repo.row_to_dict(r) for r in c.execute(
        "SELECT * FROM verifications WHERE subject_id=? AND final_label IS NULL ORDER BY created_at, rowid",
        (subject_id,)).fetchall()]


def _supersede_active(c, subject_id: str) -> None:
    for ver in _active_verifications(c, subject_id):
        verifications.add_event(c, ver["id"], "Superseded", "a newer verification replaced this one")
        repo.update_verification(c, ver["id"], final_label="SUPERSEDED", step="done")
        if ver.get("call_sid"):
            voice_port.cancel_call(ver["call_sid"])


def _set_case_status(c, case_id: str, status: str) -> None:
    c.execute("UPDATE change_cases SET status=?, updated_at=? WHERE id=?", (status, now_iso(), case_id))


def _actor(ver: dict) -> str:
    return "demo" if ver.get("source") == "simulated" else "twilio"


def _sim(ver: dict) -> dict:
    return {"verification_id": ver["id"], "simulated": ver.get("source") == "simulated"}


def _move(subject_id: str, to: Status, *, hold: HoldReason | None = None, actor: str, detail: dict) -> bool:
    try:
        return transition(subject_id, to, hold_reason=hold, actor=actor, detail=detail)
    except IllegalTransition:
        log.warning("ignored illegal transition to %s for %s", to.value, subject_id)
        return False


def request_callback(subject_id: str, kind: Literal["invoice", "change_case"]) -> str:
    """Supersedes any active verification, creates the verification row + URL token, places the call
    (or, with VOICE_MODE=simulated, a simulated line), moves CALL_PENDING → CALLING.
    On any exception placing the call: HELD(CALL_FAILED). Returns verification_id."""
    c = db.connect()
    try:
        _supersede_active(c, subject_id)
        if kind == "invoice":
            inv = repo.get_invoice(c, subject_id)
            vendor = repo.get_vendor(c, inv["vendor_id"]) if inv and inv.get("vendor_id") else None
            phone = vendor["phone_on_file"] if vendor else config.S.demo_vendor_phone   # never a number from the email
        else:
            phone = config.S.demo_vendor_phone                                             # change cases: team line only
        simulated = config.S.voice_mode != "twilio"
        ver_id, token = verifications.create(c, subject_id, kind=kind, source="simulated" if simulated else "twilio",
                                             phone_called=phone, step="created")
        ver = repo.get_verification(c, ver_id)
        audit.append(subject_id, "system", "callback_requested",
                     {"verification_id": ver_id, "phone": phone, "simulated": simulated, "kind": kind}, conn=c)
        if simulated:
            verifications.add_event(c, ver_id, "Simulated line: answer with the demo controls", step="placed")
        else:
            try:
                sid = voice_port.place_call(ver_id, token, phone)
            except Exception as e:  # noqa: BLE001
                verifications.add_event(c, ver_id, "Call failed", str(e)[:120])
                repo.update_verification(c, ver_id, final_label="SUPERSEDED", step="done")
                if kind == "invoice":
                    if _move(subject_id, Status.HELD, hold=HoldReason.CALL_FAILED, actor="system",
                             detail={"verification_id": ver_id, "error": str(e)[:120]}):
                        run_payments_agent(subject_id)                  # memo only (FR-006)
                else:
                    _set_case_status(c, subject_id, "UNCLEAR")
                return ver_id
            repo.update_verification(c, ver_id, call_sid=sid)
            verifications.add_event(c, ver_id, "Dialing", step="placed")
            audit.append(subject_id, "twilio", "call_placed", {"verification_id": ver_id, "call_sid": sid}, conn=c)
    finally:
        c.close()
    if kind == "invoice":
        _move(subject_id, Status.CALLING, actor=_actor(ver), detail=_sim(ver))
    else:
        c = db.connect()
        try:
            _set_case_status(c, subject_id, "CALLING")
        finally:
            c.close()
    return ver_id


def get_call_context(verification_id: str) -> CallContext:
    c = db.connect()
    try:
        ver = repo.get_verification(c, verification_id)
        if ver is None:
            raise KeyError(verification_id)
        if ver["kind"] == "invoice":
            inv = repo.get_invoice(c, ver["subject_id"])
            risk = inv.get("risk") or {}
            vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
            bank = bool(risk.get("bank_changed"))
            account = risk.get("proposed_account") or ""
            return CallContext(
                verification_id=verification_id, subject_id=ver["subject_id"], kind="invoice",
                payer_name=config.S.payer_name, counterparty_name=vendor["name"] if vendor else (inv.get("from_name") or "the sender"),
                amount_cents=risk.get("amount_cents"), change_type="bank_account" if bank else "other",
                expected_last4=account[-4:] if bank and len(account) >= 4 else None,
                phone_to_call=ver["phone_called"], attempts=ver.get("attempts") or 0)
        case = repo.row_to_dict(c.execute("SELECT * FROM change_cases WHERE id=?", (ver["subject_id"],)).fetchone()) or {}
        ref = case.get("account_ref") or {}
        change = case.get("requested_change") or "other"
        return CallContext(
            verification_id=verification_id, subject_id=ver["subject_id"], kind="change_case",
            payer_name=config.S.payer_name, counterparty_name=ref.get("name") or "the account",
            amount_cents=None, change_type=change if change in ("billing_contact", "payment_details", "remit_address",
                                                               "admin_contact") else "other",
            expected_last4=None, phone_to_call=config.S.demo_vendor_phone, attempts=ver.get("attempts") or 0)
    finally:
        c.close()


def question_text(ctx: CallContext) -> str:
    """The Q1 the vendor heard, word for word (PLAN.md §12.3), for the Verifier's prompt (spec 006 R10)."""
    return twiml.q1_text(ctx)


def _finalize(ver: dict, label: str, *, last4_ok: int | None = None) -> None:
    """Set final_label and apply the matching transition (§12.5). Change cases never touch invoices."""
    c = db.connect()
    try:
        verifications.finalize(c, ver["id"], label, last4_ok=last4_ok, actor=_actor(ver))
        if ver["kind"] == "change_case":
            _set_case_status(c, ver["subject_id"], CASE_OUTCOME.get(label, "UNCLEAR"))
            return
    finally:
        c.close()
    to, hold = INVOICE_OUTCOME[label]
    _move(ver["subject_id"], to, hold=hold, actor=_actor(ver), detail={**_sim(ver), "final_label": label})
    if label == "CONFIRMED":
        c = db.connect()
        try:
            risk = (repo.get_invoice(c, ver["subject_id"]) or {}).get("risk") or {}
        finally:
            c.close()
        if risk.get("bank_changed"):
            try:
                ledger.apply_vendor_bank_change(ver["subject_id"], ver["id"])
            except ledger.PolicyViolation:
                log.warning("bank change not applied for %s", ver["subject_id"])
    run_payments_agent(ver["subject_id"])


def _load_active(verification_id: str) -> dict | None:
    c = db.connect()
    try:
        ver = repo.get_verification(c, verification_id)
    finally:
        c.close()
    if ver is None or ver.get("final_label") is not None:
        return None
    try:
        if datetime.fromisoformat(ver["expires_at"].replace("Z", "+00:00")) < datetime.now(UTC):
            return None
    except (KeyError, ValueError):
        return None
    return ver


def _replay(verification_id: str) -> str:
    c = db.connect()
    try:
        ver = repo.get_verification(c, verification_id) or {}
    finally:
        c.close()
    return {"DENIED": "DENIED", "CONFIRMED": "CONFIRMED_NO_LAST4"}.get(ver.get("final_label") or "", "UNCLEAR")


def on_first_answer(verification_id: str, digits: str | None, speech: str | None,
                    confidence: float | None) -> Literal["ASK_LAST4", "DENIED", "REPROMPT", "UNCLEAR", "CONFIRMED_NO_LAST4"]:
    ver = _load_active(verification_id)
    if ver is None:
        return _replay(verification_id)                                     # type: ignore[return-value]
    if ver["step"] == "awaiting_last4":
        return "ASK_LAST4"
    if ver["step"] == "verifying":
        return "CONFIRMED_NO_LAST4"
    ctx = get_call_context(verification_id)
    channel = "dtmf" if digits else "speech"
    attempts = (ver.get("attempts") or 0) + 1
    det = voice_port.classify_answer(digits, speech)
    c = db.connect()
    try:
        repo.update_verification(c, verification_id, digits=digits, speech=speech, speech_confidence=confidence,
                                 answer_channel=channel, attempts=attempts, det_label=det, step="asked")
        verifications.add_event(c, verification_id, "Answer", f'"{speech}"' if speech else f"Pressed {digits}")
        audit.append(ver["subject_id"], _actor(ver), "answer_received",
                     {**_sim(ver), "channel": channel, "digits": digits, "speech": speech, "confidence": confidence,
                      "det_label": det, "attempt": attempts}, conn=c)
    finally:
        c.close()
    if channel == "speech":
        question, transcript, subject = question_text(ctx), speech or "", ver["subject_id"]
        start_agent("verifier", subject, lambda rctx: verifier.run_verifier(rctx, subject, question, transcript),
                    config.S.timeout_verifier_s, verifier_fallback,
                    on_done=lambda label, outcome: _store_verifier(verification_id, label, outcome))
    if det == "NO":
        _finalize(ver, "DENIED")
        return "DENIED"
    if det == "YES":
        if ctx.expected_last4:
            c = db.connect()
            try:
                repo.update_verification(c, verification_id, step="awaiting_last4")
                verifications.add_event(c, verification_id, "Last four", "Asked for the last four digits of the new account")
            finally:
                c.close()
            return "ASK_LAST4"
        if channel == "dtmf":
            _finalize(ver, "CONFIRMED")
            return "CONFIRMED_NO_LAST4"
        _enter_verifying(ver)
        return "CONFIRMED_NO_LAST4"
    if attempts < 2:
        return "REPROMPT"
    _finalize(ver, "UNCLEAR")
    return "UNCLEAR"


def _enter_verifying(ver: dict) -> None:
    c = db.connect()
    try:
        repo.update_verification(c, ver["id"], step="verifying")
    finally:
        c.close()
    if ver["kind"] == "invoice":
        _move(ver["subject_id"], Status.VERIFYING, actor=_actor(ver), detail=_sim(ver))
    JOBS.submit(await_verifier, ver["id"])


def _store_verifier(verification_id: str, label: VerifierLabel, outcome: str) -> None:
    c = db.connect()
    try:
        ver = repo.get_verification(c, verification_id)
        if ver is None:
            return
        repo.update_verification(c, verification_id, llm_label=label.label, llm_rationale=label.rationale[:200])
        audit.append(ver["subject_id"], "agent:verifier", "verifier_label",
                     {**_sim(ver), "label": label.label, "rationale": label.rationale[:200], "outcome": outcome}, conn=c)
    finally:
        c.close()


def on_last4(verification_id: str, digits: str | None) -> Literal["CONFIRMED", "MISMATCH", "NO_INPUT"]:
    ver = _load_active(verification_id)
    if ver is None or ver["step"] != "awaiting_last4":
        c = db.connect()
        try:
            v = repo.get_verification(c, verification_id) or {}
        finally:
            c.close()
        return {"LAST4_MISMATCH": "MISMATCH", "CONFIRMED": "CONFIRMED"}.get(v.get("final_label") or "",  # type: ignore[return-value]
                                                                           "CONFIRMED" if v.get("step") == "verifying" else "NO_INPUT")
    ctx = get_call_context(verification_id)
    c = db.connect()
    try:
        audit.append(ver["subject_id"], _actor(ver), "last4_checked",
                     {**_sim(ver), "entered": bool(digits),
                      "match": bool(digits) and hmac.compare_digest(digits or "", ctx.expected_last4 or "")}, conn=c)
    finally:
        c.close()
    if not digits:
        _finalize(ver, "UNCLEAR")
        return "NO_INPUT"
    if not hmac.compare_digest(digits, ctx.expected_last4 or ""):
        _finalize(ver, "LAST4_MISMATCH", last4_ok=0)
        return "MISMATCH"
    c = db.connect()
    try:
        repo.update_verification(c, verification_id, last4_ok=1)
        verifications.add_event(c, verification_id, "Last four", "Matched the requested account")
    finally:
        c.close()
    if ver.get("answer_channel") == "dtmf":
        _finalize(ver, "CONFIRMED", last4_ok=1)
    else:
        _enter_verifying({**ver, "last4_ok": 1})
    return "CONFIRMED"


def await_verifier(verification_id: str) -> None:
    """JOBS task: wait for the Verifier's label, then confirm only if it agrees (§12.5)."""
    deadline = time.monotonic() + config.S.timeout_verifier_s + 5
    while True:
        c = db.connect()
        try:
            ver = repo.get_verification(c, verification_id)
        finally:
            c.close()
        if ver is None or ver.get("final_label") is not None:
            return
        if ver.get("llm_label") or time.monotonic() >= deadline:
            break
        _poll_sleep(VERIFIER_POLL_S)
    if ver.get("llm_label") == "CONFIRMED":
        _finalize(ver, "CONFIRMED", last4_ok=ver.get("last4_ok"))
    else:
        _finalize(ver, "VERIFIER_DISAGREED")


CALL_COMPLETED = "Call completed"
PROGRESS = {"queued": ("Dialing", "placed"), "initiated": ("Dialing", "placed"),
            "ringing": ("Ringing", "ringing"), "in-progress": ("Answered", "answered")}


def on_call_status(verification_id: str, call_status: str) -> None:
    """Twilio status callbacks (and the voice fetch's "in-progress"). Idempotent (spec 006 analyze I1):
    a progress status audits and adds its timeline event only when it advances the step, and
    `completed` is handled once per verification, so retried callbacks write nothing."""
    ver = _load_active(verification_id)
    if ver is None:
        return
    if call_status in PROGRESS:
        label, step = PROGRESS[call_status]
        if STEP_ORDER.index(step) <= STEP_ORDER.index(ver["step"]):
            return
    elif call_status == "completed" and any(e.get("label") == CALL_COMPLETED for e in ver.get("events") or []):
        return
    c = db.connect()
    try:
        audit.append(ver["subject_id"], _actor(ver), "call_status", {**_sim(ver), "status": call_status}, conn=c)
        if call_status in PROGRESS:
            verifications.add_event(c, verification_id, label, step=step)
            return
        if call_status == "completed":
            verifications.add_event(c, verification_id, CALL_COMPLETED)
    finally:
        c.close()
    if call_status in ("busy", "no-answer", "failed", "canceled"):
        _finalize(ver, "NO_ANSWER")
    elif call_status == "completed":
        JOBS.submit(_after_completed, verification_id)


def _after_completed(verification_id: str) -> None:
    """Twilio can post the answer and the hang-up almost together: wait, re-read, then decide by step."""
    if COMPLETED_GRACE_S:
        time.sleep(COMPLETED_GRACE_S)
    ver = _load_active(verification_id)
    if ver is None or ver["step"] in ("verifying", "done"):
        return                                        # await_verifier (or the answer) decides
    _finalize(ver, "UNCLEAR")


def simulate_answer(subject_id: str, answer: Literal["yes", "no"], last4: str | None) -> None:
    """DEMO_MODE only (§12.6): the same code path as a real answer, with source="simulated"."""
    if not config.S.demo_mode:
        raise SimulateNotAllowed("simulate-answer is only available in DEMO_MODE")
    if answer not in ("yes", "no"):
        raise ValueError("answer must be 'yes' or 'no'")
    c = db.connect()
    try:
        inv = repo.get_invoice(c, subject_id)
        if inv is None:
            raise KeyError(subject_id)
        status, hold = inv["status"], inv.get("hold_reason")
    finally:
        c.close()
    if status == Status.HELD and hold in {r.value for r in RETRYABLE}:
        _move(subject_id, Status.CALL_PENDING, actor="demo", detail={"simulated": True, "retry": True})
        status = Status.CALL_PENDING
    elif status not in (Status.CALL_PENDING, Status.CALLING):
        raise SimulateNotAllowed(f"nothing to answer: the invoice is {status}")

    c = db.connect()
    try:
        active = _active_verifications(c, subject_id)
        reuse = (status == Status.CALLING and config.S.voice_mode != "twilio" and len(active) == 1
                 and active[0].get("source") == "simulated")
        if reuse:
            ver_id = active[0]["id"]
        else:
            _supersede_active(c, subject_id)
            vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
            ver_id, _ = verifications.create(c, subject_id, kind="invoice", source="simulated", step="placed",
                                             phone_called=vendor["phone_on_file"] if vendor else config.S.demo_vendor_phone,
                                             first_event="Simulated line: answer with the demo controls")
    finally:
        c.close()
    if status == Status.CALL_PENDING:
        _move(subject_id, Status.CALLING, actor="demo", detail={"verification_id": ver_id, "simulated": True})
    decision = on_first_answer(ver_id, "1" if answer == "yes" else "2", None, None)
    if decision == "ASK_LAST4":
        on_last4(ver_id, last4)


def retry_callback(invoice_id: str) -> str:
    if not ledger.retry_callback_allowed(invoice_id):
        raise IllegalTransition("retry is only possible for a HELD invoice with a retryable reason")
    transition(invoice_id, Status.CALL_PENDING, actor="human:reviewer", detail={"retry": True})
    return request_callback(invoice_id, "invoice")
