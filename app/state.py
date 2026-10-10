"""Invoice status machine, PLAN.md §7.3 (FROZEN after milestone A1).

transition() is an atomic compare-and-set: the UPDATE and its audit event
commit in one BEGIN IMMEDIATE transaction.
"""
from __future__ import annotations

import sqlite3
from enum import StrEnum

from app import audit, db
from app.ids import now_iso


class Status(StrEnum):
    RECEIVED = "RECEIVED"
    EXTRACTED = "EXTRACTED"
    SCORED = "SCORED"
    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REVIEW_APPROVED = "REVIEW_APPROVED"
    CALL_PENDING = "CALL_PENDING"
    CALLING = "CALLING"
    VERIFYING = "VERIFYING"
    CONFIRMED = "CONFIRMED"
    RELEASED = "RELEASED"
    HELD = "HELD"
    FAILED = "FAILED"


class HoldReason(StrEnum):
    DENIED_BY_VENDOR = "DENIED_BY_VENDOR"
    UNCLEAR_ANSWER = "UNCLEAR_ANSWER"
    NO_ANSWER = "NO_ANSWER"
    LAST4_MISMATCH = "LAST4_MISMATCH"
    VERIFIER_DISAGREED = "VERIFIER_DISAGREED"
    REVIEW_REJECTED = "REVIEW_REJECTED"
    UNKNOWN_VENDOR = "UNKNOWN_VENDOR"
    CALL_FAILED = "CALL_FAILED"
    AGENT_HOLD = "AGENT_HOLD"


S = Status
H = HoldReason

# From → allowed to (PLAN.md §7.3 table).
ALLOWED: dict[Status, set[Status]] = {
    S.RECEIVED: {S.EXTRACTED, S.FAILED},
    S.EXTRACTED: {S.SCORED, S.FAILED},
    S.SCORED: {S.AUTO_APPROVED, S.NEEDS_REVIEW, S.CALL_PENDING, S.HELD},
    S.AUTO_APPROVED: {S.RELEASED, S.HELD},
    S.NEEDS_REVIEW: {S.REVIEW_APPROVED, S.HELD},
    S.REVIEW_APPROVED: {S.RELEASED, S.HELD},
    S.CALL_PENDING: {S.CALLING, S.HELD},
    S.CALLING: {S.VERIFYING, S.CONFIRMED, S.HELD},
    S.VERIFYING: {S.CONFIRMED, S.HELD},
    S.CONFIRMED: {S.RELEASED, S.HELD},
    S.HELD: {S.CALL_PENDING},
    S.RELEASED: set(),
    S.FAILED: set(),
}

# Hold reasons allowed when moving from a given state to HELD.
HOLD_REASONS_FROM: dict[Status, set[HoldReason]] = {
    S.SCORED: {H.UNKNOWN_VENDOR},
    S.AUTO_APPROVED: {H.AGENT_HOLD},
    S.NEEDS_REVIEW: {H.REVIEW_REJECTED},
    S.REVIEW_APPROVED: {H.AGENT_HOLD},
    S.CALL_PENDING: {H.CALL_FAILED},
    S.CALLING: {H.DENIED_BY_VENDOR, H.UNCLEAR_ANSWER, H.NO_ANSWER, H.LAST4_MISMATCH},
    S.VERIFYING: {H.VERIFIER_DISAGREED, H.UNCLEAR_ANSWER},
    S.CONFIRMED: {H.AGENT_HOLD},
}

# HELD → CALL_PENDING (retry) only for these reasons.
RETRYABLE: set[HoldReason] = {H.UNCLEAR_ANSWER, H.NO_ANSWER, H.CALL_FAILED, H.VERIFIER_DISAGREED}

TERMINAL: set[Status] = {S.RELEASED, S.FAILED}


class IllegalTransition(Exception):
    pass


def legal_from_states(to: Status) -> list[Status]:
    return [frm for frm, tos in ALLOWED.items() if to in tos]


def transition(invoice_id: str, to: Status | str, *, hold_reason: HoldReason | str | None = None,
               actor: str, detail: dict | None = None,
               conn: sqlite3.Connection | None = None) -> bool:
    """Atomic compare-and-set.
    UPDATE invoices SET status=?, hold_reason=?, version=version+1, updated_at=?
     WHERE id=? AND status IN (<legal from-states for `to`>)
    Returns True if the row changed and writes an audit 'status_changed' event.
    Returns False if the invoice is already in `to` (idempotent no-op; webhooks retry).
    Raises IllegalTransition otherwise.
    HELD requires hold_reason, and hold_reason must be allowed for the from-state.
    The UPDATE and its audit event commit in one `BEGIN IMMEDIATE` transaction."""
    to = Status(to)
    reason = HoldReason(hold_reason) if hold_reason is not None else None
    if to is S.HELD and reason is None:
        raise IllegalTransition("HELD requires a hold_reason")
    if to is not S.HELD and reason is not None:
        raise IllegalTransition(f"hold_reason only applies to HELD, not {to}")

    own = conn is None
    c = conn or db.connect()
    try:
        if own:
            c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT status, hold_reason FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if row is None:
            raise IllegalTransition(f"unknown invoice {invoice_id}")
        frm = Status(row["status"])
        if frm == to and (to is not S.HELD or row["hold_reason"] == reason):
            if own:
                c.execute("COMMIT")
            return False
        if to not in ALLOWED[frm]:
            raise IllegalTransition(f"{frm} → {to} is not allowed")
        if to is S.HELD and reason not in HOLD_REASONS_FROM.get(frm, set()):
            raise IllegalTransition(f"{frm} → HELD with {reason} is not allowed")
        if frm is S.HELD and to is S.CALL_PENDING:
            current = HoldReason(row["hold_reason"]) if row["hold_reason"] else None
            if current not in RETRYABLE:
                raise IllegalTransition(f"HELD({current}) cannot be retried")

        ts = now_iso()
        cur = c.execute(
            "UPDATE invoices SET status=?, hold_reason=?, version=version+1, updated_at=? "
            "WHERE id=? AND status=?",
            (to.value, reason.value if reason else None, ts, invoice_id, frm.value),
        )
        if cur.rowcount != 1:
            raise IllegalTransition(f"concurrent change on {invoice_id}; retry")
        audit.append(invoice_id, actor, "status_changed",
                     {"from": frm.value, "to": to.value, "hold_reason": reason.value if reason else None,
                      **(detail or {})}, conn=c)
        if own:
            c.execute("COMMIT")
        return True
    except BaseException:
        if own and c.in_transaction:
            c.execute("ROLLBACK")
        raise
    finally:
        if own:
            c.close()
