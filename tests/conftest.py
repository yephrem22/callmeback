"""Test configuration: no credentials, no network, AI off, temp DB per test."""
from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator

import pytest

os.environ.setdefault("AI_MODE", "off")
os.environ.setdefault("DEMO_MODE", "1")
os.environ.setdefault("VOICE_MODE", "simulated")
os.environ.setdefault("STORAGE_MODE", "local")
os.environ["AI_MODE"] = "off"

from app import config  # noqa: E402


def _fresh_db(tmp_path) -> sqlite3.Connection:
    from app import db, seed

    os.environ["DB_PATH"] = str(tmp_path / "app.db")
    config.reload()
    db.init_db()
    conn = db.connect()
    seed.seed_vendors(conn)
    seed.seed_history(conn)
    return conn


@pytest.fixture
def db(tmp_path) -> Iterator[sqlite3.Connection]:
    os.environ["DEMO_MODE"] = "1"
    conn = _fresh_db(tmp_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def demo_mode_off(tmp_path) -> Iterator[sqlite3.Connection]:
    os.environ["DEMO_MODE"] = "0"
    conn = _fresh_db(tmp_path)
    try:
        yield conn
    finally:
        conn.close()
        os.environ["DEMO_MODE"] = "1"
        config.reload()
