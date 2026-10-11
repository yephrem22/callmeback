"""Regression (spec 005 T037): audit.append from two threads must not lock-order deadlock.

Thread A holds the SQLite write lock (db.tx) and then appends on its own connection; thread B
appends on a fresh connection at the same moment. A Python lock around the append made B hold
the Python lock while waiting on SQLite and A wait on the Python lock: a 5 s stall, then
"database is locked". SQLite's BEGIN IMMEDIATE alone serialises them.
"""
from __future__ import annotations

import threading
import time

from app import audit
from app import db as dbm


def test_append_inside_a_transaction_and_alone_do_not_deadlock(db):
    started = threading.Event()
    errors: list[BaseException] = []

    def a() -> None:
        c = dbm.connect()
        try:
            with dbm.tx(c):
                started.set()
                time.sleep(0.3)                      # let B reach its append first
                audit.append(None, "system", "demo_reset", {"who": "a"}, conn=c)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)
        finally:
            c.close()

    def b() -> None:
        started.wait(2)
        try:
            audit.append(None, "system", "demo_reset", {"who": "b"})
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=a), threading.Thread(target=b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(15)
    assert errors == []
    assert time.perf_counter() - t0 < 3.0
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 2
    assert audit.verify(db) == (True, None)
