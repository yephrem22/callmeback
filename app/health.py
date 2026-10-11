"""GET /api/health (PLAN.md §7.6; spec FR-019): the header status dots.

model.latency_ms is the median of the last 10 real model calls in agent_traces (last 5 minutes);
with none, and AI live, a timed GET /v1/models, cached for 60 seconds. storage checks
configuration only, so polling never makes a network call to object storage.
"""
from __future__ import annotations

import threading
import time

import httpx

from app import ai_mode, config, db, traces
from app.agents.model import PROVIDER
from app.ids import now_iso

PING_TTL_S = 60.0
_lock = threading.Lock()
_ping_cache: dict = {"at": 0.0, "result": None}


def _ping_models() -> tuple[bool, int | None]:
    """One timed GET {AKAMAI_BASE_URL}/models. Tests replace this (no network in the suite)."""
    if not config.S.akamai_api_key:
        return False, None
    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{config.S.akamai_base_url.rstrip('/')}/models", timeout=3.0,
                      headers={"Authorization": f"Bearer {config.S.akamai_api_key}"})
        return r.status_code == 200, int((time.perf_counter() - t0) * 1000)
    except httpx.HTTPError:
        return False, None


def _cached_ping() -> tuple[bool, int | None, str]:
    with _lock:
        if _ping_cache["result"] is not None and time.monotonic() - _ping_cache["at"] < PING_TTL_S:
            return _ping_cache["result"]
    ok, ms = _ping_models()
    result = (ok, ms, now_iso())
    with _lock:
        _ping_cache.update(at=time.monotonic(), result=result)
    return result


def reset_cache() -> None:
    with _lock:
        _ping_cache.update(at=0.0, result=None)


def _db_ok() -> bool:
    try:
        c = db.connect()
        try:
            c.execute("SELECT 1").fetchone()
        finally:
            c.close()
        return True
    except Exception:  # noqa: BLE001
        return False


def _last_provider() -> str:
    """Which provider answered the most recent model call (FR-025): akamai unless Bedrock stepped in."""
    try:
        c = db.connect()
        try:
            row = c.execute("SELECT name FROM agent_traces WHERE kind='model_call' ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            c.close()
    except Exception:  # noqa: BLE001
        return PROVIDER
    return row[0] if row and row[0] else PROVIDER


def _model() -> dict:
    provider = _last_provider()
    if ai_mode.effective_ai_mode() != "live":
        return {"ok": False, "latency_ms": None, "checked_at": None, "provider": provider}
    median = traces.median_latency_ms()
    if median is not None:
        return {"ok": True, "latency_ms": median, "checked_at": now_iso(), "provider": provider}
    ok, ms, at = _cached_ping()
    return {"ok": ok, "latency_ms": ms, "checked_at": at, "provider": provider}


def _storage_ok() -> bool:
    s = config.S
    if s.storage_mode != "s3":
        return True
    return all([s.obj_endpoint, s.obj_bucket, s.obj_access_key, s.obj_secret_key])


def health() -> dict:
    s = config.S
    return {
        "db": _db_ok(),
        "model": _model(),
        "twilio": {"configured": bool(s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number)},
        "storage": {"ok": _storage_ok()},
        "demo_mode": bool(s.demo_mode),
        "ai_mode": ai_mode.effective_ai_mode(),
        "deploy_label": s.deploy_label,
    }
