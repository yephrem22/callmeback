"""agent_traces writes and reads (data-model.md): the live "under the hood" feed.

Every summary is ≤ 200 chars and passed through masking.masked, so account and phone
numbers never reach a trace row.
"""
from __future__ import annotations

import secrets
import sqlite3
import statistics
from datetime import UTC, datetime, timedelta

from app import db
from app.ids import now_iso
from app.masking import masked

AGENTS = {"intake", "analyst", "verifier", "payments", "payments:redteam"}
KINDS = {"run_start", "model_call", "tool_call", "guard_allow", "guard_block", "run_end", "fallback", "error"}
MAX_SUMMARY = 200


def new_run_id() -> str:
    return "run_" + secrets.token_hex(5)


def _clean(summary: object) -> str | None:
    if summary is None:
        return None
    text = masked(str(summary))
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_SUMMARY else text[: MAX_SUMMARY - 1] + "…"


def write(subject_id: str, *, run_id: str, agent: str, kind: str, name: str | None = None,
          summary: object = None, duration_ms: int | None = None, conn: sqlite3.Connection | None = None) -> None:
    if agent not in AGENTS:
        raise ValueError(f"unknown trace agent: {agent}")
    if kind not in KINDS:
        raise ValueError(f"unknown trace kind: {kind}")
    close = conn is None
    c = conn or db.connect()
    try:
        c.execute(
            "INSERT INTO agent_traces (subject_id, run_id, agent, kind, name, summary, duration_ms, ts) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (subject_id, run_id, agent, kind, name, _clean(summary),
             int(duration_ms) if duration_ms is not None else None, now_iso()),
        )
    finally:
        if close:
            c.close()


def for_run(run_id: str, conn: sqlite3.Connection | None = None) -> list[dict]:
    close = conn is None
    c = conn or db.connect()
    try:
        return [dict(r) for r in c.execute(
            "SELECT * FROM agent_traces WHERE run_id=? ORDER BY id", (run_id,)).fetchall()]
    finally:
        if close:
            c.close()


def recent_model_latencies(within_s: int = 300, limit: int = 10, conn: sqlite3.Connection | None = None) -> list[int]:
    """Durations of the last `limit` successful model calls in the last `within_s` seconds."""
    since = (datetime.now(UTC) - timedelta(seconds=within_s)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    close = conn is None
    c = conn or db.connect()
    try:
        rows = c.execute(
            "SELECT duration_ms FROM agent_traces WHERE kind='model_call' AND duration_ms IS NOT NULL "
            "AND ts >= ? AND (summary IS NULL OR summary NOT LIKE 'error%') ORDER BY id DESC LIMIT ?",
            (since, limit)).fetchall()
        return [r[0] for r in rows]
    finally:
        if close:
            c.close()


def median_latency_ms(conn: sqlite3.Connection | None = None) -> int | None:
    xs = recent_model_latencies(conn=conn)
    return int(statistics.median(xs)) if xs else None
