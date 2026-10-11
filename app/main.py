"""FastAPI application entry point (PLAN.md §6: mounts routers, serves web/dist).

Minimal skeleton created by spec 002 (cloud-infra) so the VM answers /healthz;
spec 005 adds the §7.6 routers and spec 006 the /twilio/* webhooks. Keep /healthz unauthenticated
(Caddy routes it without basic auth) and mount the static dashboard last.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import api, logging_setup
from app.voice import routes as voice_routes
from app.voice import security as voice_security

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


# The Twilio webhooks (spec 006, PLAN.md §12.2–§12.3), in both voice modes. Caddy routes
# /twilio/* without basic auth; every request is authenticated by its signature and token.
app.include_router(voice_routes.router)
voice_security.install_access_log_redaction()        # tokens never reach the access log (analyze D1)
voice_security.warn_if_insecure()

# Static dashboard, mounted after every router so /api/* and /twilio/* win (PLAN.md §14.5).
if (WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(WEB_DIST), html=True), name="web")
