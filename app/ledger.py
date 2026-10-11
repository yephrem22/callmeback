"""Ledger (PLAN.md §13.1): the single release-eligibility check, release in one
transaction, idempotent hold, review decisions, and vendor-master change
control. Money only moves to a destination in the vendor master, and the
vendor master only changes through a verified callback."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app import audit, config, db, repo
from app.ids import new_id
from app.state import RETRYABLE, HoldReason, IllegalTransition, Status, transition

CHICAGO = ZoneInfo("America/Chicago")
RELEASABLE_STATES = {Status.AUTO_APPROVED, Status.REVIEW_APPROVED, Status.CONFIRMED}


class PolicyViolation(Exception):
    """Raised when a release is attempted that policy does not allow."""


def audit_actor(by: str) -> str:
    """Map a `released_by`/`by` value onto a PLAN.md §13.3 audit actor."""
    if by in audit.ACTORS:
        return by
    if by.startswith("policy"):
        return "policy"
    if by.startswith("agent:"):
        return "agent:payments"
    return "system"


def next_business_day(d: date) -> date:
    """The next calendar day that is not a Saturday or Sunday (holidays not modelled)."""
    n = d + timedelta(days=1)
    while n.weekday() >= 5:
        n += timedelta(days=1)
    return n


def _chicago_hhmm(ts: str | None) -> str:
    if not ts:
        return "unknown time"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(CHICAGO).strftime("%H:%M")
    except ValueError:
        return ts


def _held_reason_text(inv: dict, ver: dict | None) -> str:
    reason = inv.get("hold_reason")
    when = _chicago_hhmm(ver.get("updated_at")) if ver and ver.get("updated_at") else None
    texts = {
        "DENIED_BY_VENDOR": f"vendor denied the change on the {when} call" if when else "vendor denied the change on the callback",
        "UNCLEAR_ANSWER": "the vendor's answer was unclear",
        "NO_ANSWER": "the vendor did not answer the call",
        "LAST4_MISMATCH": "the last four digits did not match the requested account",
        "VERIFIER_DISAGREED": "the verifier did not confirm the spoken answer",
        "REVIEW_REJECTED": "a reviewer rejected it",
        "UNKNOWN_VENDOR": "there is no vendor record, so no trusted number to call",
        "CALL_FAILED": "the verification call failed",
        "AGENT_HOLD": "the Payments agent held it",
    }
    return f"invoice is HELD ({texts.get(reason, reason or 'no reason recorded')})"


def can_release(invoice_id: str, conn: sqlite3.Connection | None = None) -> tuple[bool, str]:
    """Re-reads the invoice and its latest verification. Returns (ok, human reason)."""
    close = conn is None
    c = conn or db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        if inv is None:
            return False, f"unknown invoice {invoice_id}"
        risk = inv.get("risk") or {}
        status = inv["status"]
        ver = repo.latest_verification(c, invoice_id)

        if status == Status.AUTO_APPROVED:
            if risk.get("tier") == "GREEN" and risk.get("action") == "AUTO_RELEASE":
                return True, "GREEN invoice with no flags; policy auto-release"
            return False, f"AUTO_APPROVED but risk is {risk.get('tier')}/{risk.get('action')}, not GREEN/AUTO_RELEASE"

        if status == Status.REVIEW_APPROVED:
            review = inv.get("review") or {}
            if risk.get("action") == "REVIEW" and review.get("decision") == "approve":
                return True, "approved by a human reviewer"
            return False, "REVIEW_APPROVED without a recorded approve decision for a REVIEW action"

        if status == Status.CONFIRMED:
            if ver is None:
                return False, "CONFIRMED but no verification record exists"
            if ver.get("final_label") != "CONFIRMED":
                return False, f"latest verification is {ver.get('final_label') or 'not final'}, not CONFIRMED"
            if ver.get("source") == "simulated" and not config.S.demo_mode:
                return False, "simulated verification not accepted outside DEMO_MODE"
            if ver.get("source") not in ("twilio", "simulated"):
                return False, f"verification source {ver.get('source')!r} is not trusted"
            if risk.get("bank_changed") and ver.get("last4_ok") != 1:
                return False, "bank change confirmed without a last-four match"
            how = "keypad" if ver.get("answer_channel") == "dtmf" else "spoken answer"
            sim = " (simulated)" if ver.get("source") == "simulated" else ""
            return True, f"vendor confirmed by {how} on the {_chicago_hhmm(ver.get('updated_at'))} call{sim}"

        if status == Status.HELD:
            return False, _held_reason_text(inv, ver)
        if status == Status.RELEASED:
            return False, "invoice is already RELEASED"
        return False, f"status {status} is not releasable"
    finally:
        if close:
            c.close()


def release(invoice_id: str, by: str, conn: sqlite3.Connection | None = None) -> str:
    """Release in ONE transaction: re-check, insert the payment (destination from
    the vendor master, never the email), transition to RELEASED, audit."""
    close = conn is None
    c = conn or db.connect()
    actor = audit_actor(by)
    try:
        with db.tx(c):
            ok, reason = can_release(invoice_id, conn=c)
            if not ok:
                audit.append(invoice_id, "policy", "release_blocked", {"reason": reason, "by": by}, conn=c)
                # the audit row must survive the raise: commit this transaction, then raise
                c.execute("COMMIT")
                c.execute("BEGIN IMMEDIATE")
                raise PolicyViolation(reason)
            inv = repo.get_invoice(c, invoice_id)
            risk = inv.get("risk") or {}
            vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
            if vendor is None:
                raise PolicyViolation("no vendor master record; nothing to pay to")
            today = datetime.now(CHICAGO).date()
            pay_id = new_id("pay_")
            repo.insert_payment(
                c, id=pay_id, invoice_id=invoice_id, amount_cents=int(risk.get("amount_cents") or 0),
                bank_name=vendor["bank_name"], routing=vendor["routing"], account=vendor["account"],
                method="ACH-CCD", effective_date=next_business_day(today).isoformat(), released_by=by,
            )
            transition(invoice_id, Status.RELEASED, actor=actor, detail={"payment_id": pay_id}, conn=c)
            audit.append(invoice_id, actor, "payment_released",
                         {"payment_id": pay_id, "amount_cents": int(risk.get("amount_cents") or 0),
                          "bank_name": vendor["bank_name"], "routing": vendor["routing"],
                          "account": vendor["account"], "effective_date": next_business_day(today).isoformat(),
                          "by": by, "reason": reason}, conn=c)
        return pay_id
    finally:
        if close:
            c.close()


def hold(invoice_id: str, reason: str, by: str = "agent:payments", conn: sqlite3.Connection | None = None) -> bool:
    """Idempotent. From a releasable state → HELD(AGENT_HOLD); already HELD → hold_confirmed."""
    close = conn is None
    c = conn or db.connect()
    actor = audit_actor(by)
    try:
        inv = repo.get_invoice(c, invoice_id)
        if inv is None:
            raise IllegalTransition(f"unknown invoice {invoice_id}")
        status = Status(inv["status"])
        if status in RELEASABLE_STATES:
            return transition(invoice_id, Status.HELD, hold_reason=HoldReason.AGENT_HOLD, actor=actor,
                              detail={"reason": reason}, conn=c)
        if status is Status.HELD:
            audit.append(invoice_id, actor, "hold_confirmed", {"reason": reason}, conn=c)
            return False
        raise IllegalTransition(f"cannot hold an invoice in {status}")
    finally:
        if close:
            c.close()


def record_review(invoice_id: str, decision: Literal["approve", "reject"], note: str = "",
                  by: str = "human:reviewer", conn: sqlite3.Connection | None = None) -> str:
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be 'approve' or 'reject'")
    close = conn is None
    c = conn or db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        if inv is None or inv["status"] != Status.NEEDS_REVIEW:
            raise IllegalTransition("review is only possible while NEEDS_REVIEW")
        from app.ids import now_iso
        review = {"decision": decision, "note": note or "", "at": now_iso()}
        with db.tx(c):
            repo.update_invoice(c, invoice_id, review=review)
            audit.append(invoice_id, by, "review_decision", review, conn=c)
            if decision == "approve":
                transition(invoice_id, Status.REVIEW_APPROVED, actor=by, detail={"note": note}, conn=c)
                return Status.REVIEW_APPROVED.value
            transition(invoice_id, Status.HELD, hold_reason=HoldReason.REVIEW_REJECTED, actor=by,
                       detail={"note": note}, conn=c)
            return Status.HELD.value
    finally:
        if close:
            c.close()


def retry_callback_allowed(invoice_id: str, conn: sqlite3.Connection | None = None) -> bool:
    close = conn is None
    c = conn or db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        return bool(inv and inv["status"] == Status.HELD and inv.get("hold_reason") in {r.value for r in RETRYABLE})
    finally:
        if close:
            c.close()


def apply_vendor_bank_change(invoice_id: str, verification_id: str,
                             conn: sqlite3.Connection | None = None) -> bool:
    """After a CONFIRMED verification with a last-four match on a bank-change
    invoice: write history (old → new), update the vendor master, audit.
    Idempotent per verification. Returns True if the vendor was updated."""
    close = conn is None
    c = conn or db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        if inv is None:
            raise PolicyViolation(f"unknown invoice {invoice_id}")
        if repo.bank_history_for_verification(c, verification_id):
            return False
        risk = inv.get("risk") or {}
        ver = repo.get_verification(c, verification_id)
        if inv["status"] != Status.CONFIRMED:
            raise PolicyViolation(f"vendor master can only change on a CONFIRMED invoice, not {inv['status']}")
        if not risk.get("bank_changed"):
            raise PolicyViolation("invoice did not request a bank change")
        if ver is None or ver.get("subject_id") != invoice_id:
            raise PolicyViolation("verification does not belong to this invoice")
        if ver.get("final_label") != "CONFIRMED" or ver.get("last4_ok") != 1:
            raise PolicyViolation("bank change requires a CONFIRMED verification with a last-four match")
        if ver.get("source") == "simulated" and not config.S.demo_mode:
            raise PolicyViolation("simulated verification not accepted outside DEMO_MODE")
        vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
        if vendor is None:
            raise PolicyViolation("no vendor record to update")
        new_bank, new_routing, new_account = (risk.get("proposed_bank_name"), risk.get("proposed_routing"),
                                              risk.get("proposed_account"))
        if not (new_routing or new_account):
            raise PolicyViolation("no proposed bank details recorded")
        new_routing = new_routing or vendor["routing"]
        new_account = new_account or vendor["account"]
        with db.tx(c):
            repo.insert_bank_history(
                c, vendor_id=vendor["id"], old_bank_name=vendor["bank_name"], old_routing=vendor["routing"],
                old_account=vendor["account"], new_bank_name=new_bank, new_routing=new_routing,
                new_account=new_account, invoice_id=invoice_id, verification_id=verification_id)
            repo.update_vendor_bank(c, vendor["id"], new_bank, new_routing, new_account)
            msg = (f"Vendor master updated: {vendor['bank_name']} ••••{vendor['account'][-4:]} → "
                   f"{new_bank} ••••{new_account[-4:]} (verified by callback, {_chicago_hhmm(ver.get('updated_at'))})")
            audit.append(invoice_id, "policy", "vendor_bank_updated",
                         {"vendor_id": vendor["id"], "old_bank_name": vendor["bank_name"],
                          "old_routing": vendor["routing"], "old_account": vendor["account"],
                          "new_bank_name": new_bank, "new_routing": new_routing, "new_account": new_account,
                          "verification_id": verification_id, "message": msg}, conn=c)
        return True
    finally:
        if close:
            c.close()
