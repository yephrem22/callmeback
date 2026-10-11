"""Serving the built dashboard (spec 007 FR-024; contracts/serving.md): files, the app-shell fallback
for client paths, and real 404s for API-ish paths."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_web

SHELL = "<!doctype html><div id=root></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text(SHELL)
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def client(dist):
    app = FastAPI()

    @app.get("/api/real")
    def real() -> dict:
        return {"ok": True}

    mount_web(app, dist)
    return TestClient(app)


def test_files_and_root(client):
    assert client.get("/").text == SHELL
    r = client.get("/assets/app.js")
    assert r.status_code == 200 and r.text == "console.log(1)"
    assert client.get("/api/real").json() == {"ok": True}          # routers win over the mount


@pytest.mark.parametrize("path", ["/some/client/path", "/gallery", "/cases/cc_123"])
def test_client_paths_get_the_app_shell(client, path):
    r = client.get(path)
    assert r.status_code == 200 and r.text == SHELL


@pytest.mark.parametrize("path", ["/api/nope", "/twilio/nope", "/internal/nope", "/mcp", "/mcp/x", "/healthz/x",
                                  "/assets/missing.js"])
def test_api_and_asset_paths_keep_their_404(client, path):
    r = client.get(path)
    assert r.status_code == 404 and r.text != SHELL


def test_non_get_is_not_the_shell(client):
    r = client.post("/some/client/path")
    assert r.status_code in (404, 405) and r.text != SHELL


def test_nothing_mounted_without_a_build(tmp_path):
    app = FastAPI()
    mount_web(app, tmp_path)                                         # no index.html
    assert TestClient(app).get("/").status_code == 404
