"""FastAPI application entry point (PLAN.md §6: mounts routers, serves web/dist).

Minimal skeleton created by spec 002 (cloud-infra) so the VM answers /healthz;
spec 005 (Builder A) adds the §7.6 routers here. Keep /healthz unauthenticated
(Caddy routes it without basic auth) and mount the static dashboard last.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import api, logging_setup
from app.config import S

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = REPO_ROOT / "web" / "dist"

logging_setup.configure()
app = FastAPI(title="Call Me Back", docs_url=None, redoc_url=None)


@app.get("/healthz")
def healthz() -> dict:
    """Liveness (PLAN.md §7.6)."""
    return {"ok": True}


# The dashboard API (spec 005). No SPA fallback here: that belongs to spec 007 (analyze A3).
app.include_router(api.router)


# Builder B's throwaway Twilio spike (spec 002 milestone B2, DEMO_MODE only); spec 006 removes it.
if S.demo_mode:
    try:
        from app.voice.spike import router as spike_router
    except ImportError:
        spike_router = None
    if spike_router is not None:
        app.include_router(spike_router)

# Static dashboard, mounted after every router so /api/* and /twilio/* win (PLAN.md §14.5).
if (WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
