"""Test and fixture helpers (research R7): finalised verification rows and
walking an invoice through legal transitions."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
from collections import deque
from datetime import UTC, datetime, timedelta

from app import config, repo
from app.ids import new_id, now_iso
from app.state import ALLOWED, HOLD_REASONS_FROM, HoldReason, Status, transition


def make_verification(conn: sqlite3.Connection, subject_id: str, *, final_label: str,
                      source: str = "simulated", last4_ok: int | None = None, kind: str = "invoice",
                      step: str = "done", phone_called: str | None = None, det_label: str | None = None,
                      speech: str | None = None, digits: str | None = None, llm_label: str | None = None,
                      confidence: float | None = None, events: list[dict] | None = None) -> str:
    ver_id = new_id("ver_")
    token = secrets.token_urlsafe(24)
    channel = "dtmf" if digits else ("speech" if speech else None)
    ts = now_iso()
    repo.insert_verification(
        conn, id=ver_id, subject_id=subject_id, kind=kind,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=(datetime.now(UTC) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        call_sid=None if source == "simulated" else "CA" + secrets.token_hex(16),
        phone_called=phone_called or config.S.demo_vendor_phone, source=source, step=step, attempts=1,
        answer_channel=channel, digits=digits, speech=speech, speech_confidence=confidence,
        det_label=det_label, llm_label=llm_label, last4_ok=last4_ok, final_label=final_label,
        events=events or [{"ts": ts, "label": "Dialing", "detail": ""}, {"ts": ts, "label": "Answered", "detail": ""}],
    )
    return ver_id


def _path(frm: Status, to: Status) -> list[Status]:
    """Shortest legal path of statuses from `frm` to `to` (excluding frm)."""
    q = deque([[frm]])
    seen = {frm}
    while q:
        path = q.popleft()
        if path[-1] == to:
            return path[1:]
        for nxt in ALLOWED[path[-1]]:
            # HELD needs a reason tied to the from-state and is only retryable for four
            # reasons, so it is never used as an intermediate step.
            if nxt is Status.HELD and nxt is not to:
                continue
            if nxt not in seen:
                seen.add(nxt)
                q.append(path + [nxt])
    raise ValueError(f"no legal path {frm} → {to}")


def drive_to(conn: sqlite3.Connection, invoice_id: str, status: Status | str,
             hold_reason: HoldReason | str | None = None, actor: str = "system") -> None:
    """Walk the invoice through legal transitions to `status`."""
    target = Status(status)
    inv = repo.get_invoice(conn, invoice_id)
    frm = Status(inv["status"])
    if target is Status.HELD:
        reason = HoldReason(hold_reason) if hold_reason else None
        if reason is None:
            raise ValueError("drive_to HELD needs a hold_reason")
        if frm is Status.HELD:
            return
        # pick a from-state that allows this hold reason and is reachable
        candidates = [s for s, rs in HOLD_REASONS_FROM.items() if reason in rs]
        for cand in sorted(candidates, key=lambda s: len(_path(frm, s)) if _reachable(frm, s) else 99):
            if _reachable(frm, cand):
                for step in _path(frm, cand):
                    transition(invoice_id, step, actor=actor, conn=conn)
                transition(invoice_id, Status.HELD, hold_reason=reason, actor=actor, conn=conn)
                return
        raise ValueError(f"cannot reach HELD({reason}) from {frm}")
    for step in _path(frm, target):
        transition(invoice_id, step, actor=actor, conn=conn)


def _reachable(frm: Status, to: Status) -> bool:
    try:
        _path(frm, to)
        return True
    except ValueError:
        return frm == to
