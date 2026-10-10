"""Identifiers and timestamps (PLAN.md §6 conventions).

A deterministic mode exists for the fixtures exporter so re-running it
produces identical files: ids become prefix + a counter, and the clock
advances one second per call from a fixed start."""
from __future__ import annotations

import secrets
import threading
from datetime import UTC, datetime, timedelta

_LOCK = threading.Lock()
_DET: dict | None = None   # {"counter": int, "clock": datetime, "step": timedelta}


def new_id(prefix: str) -> str:
    """A prefix plus a random suffix, e.g. 'inv_' + secrets.token_hex(5)."""
    if _DET is not None:
        with _LOCK:
            _DET["counter"] += 1
            return f"{prefix}fixture{_DET['counter']:02d}"
    return prefix + secrets.token_hex(5)


def now_iso() -> str:
    """UTC ISO-8601 with a trailing Z and second precision."""
    if _DET is not None:
        with _LOCK:
            _DET["clock"] += _DET["step"]
            return _DET["clock"].isoformat().replace("+00:00", "Z")
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def set_deterministic(start: str | None = "2026-10-10T15:00:00Z", step_seconds: int = 1) -> None:
    """Enable (or, with start=None, disable) deterministic ids and clock."""
    global _DET
    if start is None:
        _DET = None
        return
    _DET = {"counter": 0, "clock": datetime.fromisoformat(start.replace("Z", "+00:00")),
            "step": timedelta(seconds=step_seconds)}
