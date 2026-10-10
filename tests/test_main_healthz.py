"""app/main.py skeleton: /healthz answers, nothing internal is mounted (spec 002)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_healthz():
    r = TestClient(app).get("/healthz")
    assert r.status_code == 200 and r.json() == {"ok": True}


def test_internal_routes_are_not_mounted_by_the_skeleton():
    assert TestClient(app).get("/internal/change-cases").status_code == 404
