"""Audit log, phase-1 stub with the final signatures. Phase 2 (T017) adds the
sha256 chain; the append discipline (process lock + BEGIN IMMEDIATE, or join
the caller's transaction) is already final.

PLAN.md §13.2, §13.3.
"""
from __future__ import annotations

import json
import sqlite3
import threading

from app import db
from app.ids import now_iso
from app.masking import masked

_LOCK = threading.Lock()

ACTORS = {
    "system", "policy", "agent:intake", "agent:analyst", "agent:verifier", "agent:payments",
    "plugin:payment-guard", "human:reviewer", "twilio", "devrev", "demo",
}

EVENTS = {
    "invoice_received", "raw_stored", "extraction_done", "extraction_mismatch", "vendor_resolved",
    "risk_scored", "status_changed", "analyst_report", "callback_requested", "call_placed",
    "call_status", "answer_received", "verifier_label", "last4_checked", "verification_final",
    "vendor_bank_updated", "review_decision", "guard_allowed", "guard_blocked", "release_blocked",
    "payment_released", "hold_confirmed", "memo_written", "webhook_rejected", "ai_fallback",
    "ai_mode_changed", "change_case_created", "change_case_duplicate", "demo_reset",
}


def _canon(data: dict) -> str:
    return json.dumps(masked(data), sort_keys=True, separators=(",", ":"))


def append(subject_id: str | None, actor: str, event: str, data: dict,
           conn: sqlite3.Connection | None = None) -> int:
    """Append one entry. Serialised by a process-wide lock and written inside
    BEGIN IMMEDIATE, so two writers can never read the same last row. When
    `conn` is already inside a transaction, the entry joins it."""
    if actor not in ACTORS:
        raise ValueError(f"unknown audit actor: {actor}")
    if event not in EVENTS:
        raise ValueError(f"unknown audit event: {event}")
    close = conn is None
    c = conn or db.connect()
    own = close or not c.in_transaction
    with _LOCK:
        try:
            if own:
                c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT seq FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            seq = (row["seq"] + 1) if row else 1
            c.execute(
                "INSERT INTO audit_log (seq, ts, subject_id, actor, event, data, prev_hash, hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (seq, now_iso(), subject_id, actor, event, _canon(data), "0" * 64, ""),
            )
            if own:
                c.execute("COMMIT")
            return seq
        except BaseException:
            if own and c.in_transaction:
                c.execute("ROLLBACK")
            raise
        finally:
            if close:
                c.close()


def verify() -> tuple[bool, int | None]:
    """Fail closed until the hash chain exists (phase 2, T017)."""
    return False, None
