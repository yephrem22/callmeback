"""One-time URL tokens (PLAN.md §12.1, §12.2 steps 3–4).

Only the sha256 of a token is stored. A token is `expired` when unknown, past `expires_at`
(15 minutes) or SUPERSEDED; `final` when its verification already has a label (a retried
webhook replays the script); otherwise `active`. A webhook's CallSid must match the stored one;
if none is stored yet (the first-fetch race) it is stored.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from app import db, repo
from app.verifications import new_token  # noqa: F401  (PLAN.md §7.5: exposed by app/voice)

State = Literal["active", "final", "expired"]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _expired(ver: dict) -> bool:
    try:
        return datetime.fromisoformat(ver["expires_at"].replace("Z", "+00:00")) < datetime.now(UTC)
    except (KeyError, AttributeError, ValueError):
        return True                                   # unreadable expiry: fail closed


def lookup(token: str) -> tuple[dict | None, State]:
    c = db.connect()
    try:
        ver = repo.row_to_dict(c.execute("SELECT * FROM verifications WHERE token_hash=?",
                                         (hash_token(token),)).fetchone())
    finally:
        c.close()
    if ver is None or ver.get("final_label") == "SUPERSEDED" or _expired(ver):
        return ver, "expired"
    if ver.get("final_label"):
        return ver, "final"
    return ver, "active"


def match_call(ver: dict, call_sid: str | None) -> bool:
    """True when the webhook belongs to this verification's call (storing the SID on first sight)."""
    if not call_sid:
        return False
    stored = ver.get("call_sid")
    if stored:
        return stored == call_sid
    c = db.connect()
    try:
        # only fill an empty slot: a concurrent first fetch cannot overwrite a stored SID
        c.execute("UPDATE verifications SET call_sid=? WHERE id=? AND call_sid IS NULL", (call_sid, ver["id"]))
        row = c.execute("SELECT call_sid FROM verifications WHERE id=?", (ver["id"],)).fetchone()
    finally:
        c.close()
    ver["call_sid"] = row[0] if row else None
    return ver["call_sid"] == call_sid
