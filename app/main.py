"""FastAPI application entry point (PLAN.md §6: mounts routers, serves web/dist).

Minimal skeleton created by spec 002 (cloud-infra) so the VM answers /healthz;
spec 005 adds the §7.6 routers and spec 006 the /twilio/* webhooks. Keep /healthz unauthenticated
(Caddy routes it without basic auth) and mount the static dashboard last.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.types import Scope

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

RESERVED = ("api/", "twilio/", "internal/", "mcp", "healthz", "assets/")


class SpaStaticFiles(StaticFiles):
    """web/dist with an app-shell fallback (spec 007 FR-024, contracts/serving.md): a GET for a path that
    is not a file returns index.html, except API-ish and asset paths, which keep their real 404."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            if e.status_code != 404 or scope.get("method") not in ("GET", "HEAD") or path.startswith(RESERVED):
                raise
            return await super().get_response("index.html", scope)


def mount_web(target: FastAPI, dist: Path) -> None:
    """Mount the built dashboard at / (call after every router, so /api/* and /twilio/* win)."""
    if (dist / "index.html").is_file():
        target.mount("/", SpaStaticFiles(directory=str(dist), html=True), name="web")


# Static dashboard, mounted after every router (PLAN.md §14.5).
mount_web(app, WEB_DIST)
