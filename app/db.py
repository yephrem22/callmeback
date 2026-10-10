"""SQLite access (PLAN.md §6, §7.2): WAL mode, one connection per unit of
work, explicit BEGIN IMMEDIATE transactions. The schema is app/schema.sql,
a byte-identical copy of specs/003-core-engine/contracts/schema.sql."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app import config

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    """A fresh connection in autocommit mode; use tx() for transactions."""
    path = config.S.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create every table from the frozen schema. Idempotent."""
    conn = connect()
    try:
        conn.executescript(SCHEMA_PATH.read_text())
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT, rolling back on any exception."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def in_transaction(conn: sqlite3.Connection) -> bool:
    return conn.in_transaction
