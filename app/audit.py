"""Hash-chained audit log (PLAN.md §13.2, §13.3).

Every entry is sha256(prev_hash + "|" + canonical JSON of the entry body).
Appends are serialised by a process-wide lock inside BEGIN IMMEDIATE, or join
the caller's open transaction so a status change and its event commit together.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading

from app import db
from app.ids import now_iso
from app.masking import masked

_LOCK = threading.Lock()
GENESIS = "0" * 64

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


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + "|" + _canon(body)).encode()).hexdigest()


def append(subject_id: str | None, actor: str, event: str, data: dict,
           conn: sqlite3.Connection | None = None) -> int:
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
            last = c.execute("SELECT seq, hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            seq = (last["seq"] + 1) if last else 1
            prev = last["hash"] if last else GENESIS
            ts = now_iso()
            body = {"seq": seq, "ts": ts, "subject_id": subject_id, "actor": actor, "event": event,
                    "data": masked(data or {})}
            h = _hash(prev, body)
            c.execute(
                "INSERT INTO audit_log (seq, ts, subject_id, actor, event, data, prev_hash, hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (seq, ts, subject_id, actor, event, _canon(body["data"]), prev, h),
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


def verify(conn: sqlite3.Connection | None = None) -> tuple[bool, int | None]:
    """Recompute the chain in seq order. Returns (ok, first broken seq)."""
    close = conn is None
    c = conn or db.connect()
    try:
        prev = GENESIS
        expected_seq = 1
        for r in c.execute("SELECT seq, ts, subject_id, actor, event, data, prev_hash, hash "
                           "FROM audit_log ORDER BY seq").fetchall():
            if r["seq"] != expected_seq or r["prev_hash"] != prev:
                return False, r["seq"]
            try:
                data = json.loads(r["data"])
            except json.JSONDecodeError:
                return False, r["seq"]
            body = {"seq": r["seq"], "ts": r["ts"], "subject_id": r["subject_id"], "actor": r["actor"],
                    "event": r["event"], "data": data}
            if _hash(prev, body) != r["hash"]:
                return False, r["seq"]
            prev = r["hash"]
            expected_seq += 1
        return True, None
    finally:
        if close:
            c.close()


def _summary(event: str, data: dict) -> str:
    if event == "status_changed":
        s = f"{data.get('from')} → {data.get('to')}"
        return s + (f" ({data['hold_reason']})" if data.get("hold_reason") else "")
    if event == "risk_scored":
        return f"{data.get('points')} points, {data.get('tier')}, {data.get('action')}"
    if event == "vendor_resolved":
        return f"{data.get('vendor_name') or 'no vendor'} ({data.get('sender_status')})"
    for key in ("reason", "message", "summary", "label", "decision"):
        if data.get(key):
            return str(data[key])[:120]
    return event.replace("_", " ")


def list_entries(subject_id: str | None = None, limit: int = 200,
                 conn: sqlite3.Connection | None = None) -> list[dict]:
    close = conn is None
    c = conn or db.connect()
    try:
        if subject_id:
            rows = c.execute("SELECT * FROM audit_log WHERE subject_id=? ORDER BY seq", (subject_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM (SELECT * FROM audit_log ORDER BY seq DESC LIMIT ?) ORDER BY seq",
                             (limit,)).fetchall()
        out = []
        for r in rows:
            data = json.loads(r["data"])
            out.append({"seq": r["seq"], "ts": r["ts"], "subject_id": r["subject_id"], "actor": r["actor"],
                        "event": r["event"], "data": data, "summary": _summary(r["event"], data),
                        "hash_short": r["hash"][:6], "hash": r["hash"], "prev_hash": r["prev_hash"]})
        return out
    finally:
        if close:
            c.close()
