"""Verification-row primitives shared by the fixtures exporter, the tests and
(later) spec 005/006's pipeline: create a row with a hashed token, append
timeline events, and finalise it with a label (PLAN.md §7.2, §12.5)."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta

from app import audit, config, db, repo
from app.ids import new_id, now_iso

TOKEN_TTL_MIN = 15


def new_token() -> tuple[str, str]:
    """(token, sha256_hex). Only the hash is stored."""
    token = secrets.token_urlsafe(24)
    return token, hashlib.sha256(token.encode()).hexdigest()


def create(conn: sqlite3.Connection, subject_id: str, *, kind: str = "invoice", source: str = "simulated",
           phone_called: str | None = None, call_sid: str | None = None, step: str = "created",
           first_event: str | None = None) -> tuple[str, str]:
    """Insert a verification row. Returns (verification_id, token)."""
    token, token_hash = new_token()
    ver_id = new_id("ver_")
    expires = (datetime.now(UTC) + timedelta(minutes=TOKEN_TTL_MIN)).replace(microsecond=0)
    events = [{"ts": now_iso(), "label": first_event, "detail": ""}] if first_event else []
    repo.insert_verification(
        conn, id=ver_id, subject_id=subject_id, kind=kind, token_hash=token_hash,
        expires_at=expires.isoformat().replace("+00:00", "Z"), call_sid=call_sid,
        phone_called=phone_called or config.S.demo_vendor_phone, source=source, step=step, events=events,
    )
    return ver_id, token


def add_event(conn: sqlite3.Connection, ver_id: str, label: str, detail: str = "",
              step: str | None = None) -> None:
    """Append a timeline event. The read-modify-write of the JSON list runs inside one write
    transaction (or the caller's), so concurrent webhooks never lose each other's events."""
    with db.tx(conn) if not conn.in_transaction else _noop():
        ver = repo.get_verification(conn, ver_id)
        events = list(ver.get("events") or [])
        events.append({"ts": now_iso(), "label": label, "detail": detail})
        cols = {"events": events}
        if step:
            cols["step"] = step
        repo.update_verification(conn, ver_id, **cols)


def record_answer(conn: sqlite3.Connection, ver_id: str, *, digits: str | None = None,
                  speech: str | None = None, confidence: float | None = None, det_label: str | None = None,
                  llm_label: str | None = None, llm_rationale: str | None = None) -> None:
    ver = repo.get_verification(conn, ver_id)
    repo.update_verification(
        conn, ver_id, digits=digits, speech=speech, speech_confidence=confidence, det_label=det_label,
        llm_label=llm_label, llm_rationale=llm_rationale,
        answer_channel="dtmf" if digits else ("speech" if speech else ver.get("answer_channel")),
        attempts=(ver.get("attempts") or 0) + 1, step="asked" if ver.get("step") in ("created", "placed", "ringing", "answered") else ver.get("step"),
    )


def finalize(conn: sqlite3.Connection, ver_id: str, final_label: str, *, last4_ok: int | None = None,
             actor: str = "system", detail: str = "") -> None:
    """Set final_label, step='done', append the event and audit verification_final.
    Does NOT transition the invoice; the caller decides (PLAN.md §12.5)."""
    ver = repo.get_verification(conn, ver_id)
    if ver is None:
        raise ValueError(f"unknown verification {ver_id}")
    events = list(ver.get("events") or [])
    events.append({"ts": now_iso(), "label": "Verdict", "detail": detail or final_label})
    cols = {"final_label": final_label, "step": "done", "events": events}
    if last4_ok is not None:
        cols["last4_ok"] = last4_ok
    with db.tx(conn) if not conn.in_transaction else _noop():
        repo.update_verification(conn, ver_id, **cols)
        audit.append(ver["subject_id"], actor, "verification_final",
                     {"verification_id": ver_id, "final_label": final_label, "last4_ok": last4_ok,
                      "source": ver.get("source"), "simulated": ver.get("source") == "simulated"}, conn=conn)


class _noop:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False
