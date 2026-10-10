"""Identifiers and timestamps (PLAN.md §6 conventions)."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime


def new_id(prefix: str) -> str:
    """A prefix plus a random suffix, e.g. 'inv_' + secrets.token_hex(5)."""
    return prefix + secrets.token_hex(5)


def now_iso() -> str:
    """UTC ISO-8601 with a trailing Z and second precision."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
