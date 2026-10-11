"""Effective AI mode (research R10): AI_MODE at start, overridable at runtime in DEMO_MODE.

`run_agent` reads it at the start of every run, so a toggle takes effect for new runs while
in-flight runs finish or fall back on their own.
"""
from __future__ import annotations

import threading

from app import audit, config

_lock = threading.Lock()
_override: str | None = None


def effective_ai_mode() -> str:
    with _lock:
        mode = _override
    return mode if mode is not None else ("live" if config.S.ai_mode == "live" else "off")


def set_ai_mode(mode: str, *, actor: str = "demo", record: bool = True) -> str:
    global _override
    if mode not in ("live", "off"):
        raise ValueError("mode must be 'live' or 'off'")
    before = effective_ai_mode()
    with _lock:
        _override = mode
    if record:
        audit.append(None, actor, "ai_mode_changed", {"from": before, "to": mode})
    return mode


def reset_override() -> None:
    global _override
    with _lock:
        _override = None
