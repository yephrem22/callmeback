"""Found on the first live call (T017): Twilio's voice fetch and its own 'answered' status callback
arrive together, and both wrote "Answered" plus a call_status audit row. The step check and the
write must happen in one transaction, and timeline appends must never lose an event."""
from __future__ import annotations

import threading
import time

from app import db as dbm
from app import pipeline, repo, verifications
from tests.twilio_helpers import calling, latest


def _race(n: int, fn) -> list[BaseException]:
    barrier, errors = threading.Barrier(n), []

    def run(i: int) -> None:
        try:
            barrier.wait(5)
            fn(i)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    return errors


def test_simultaneous_answered_callbacks_write_one_event(db, twilio_env, monkeypatch):
    iid = calling("02_acme_fraud")
    ver_id = latest(db, iid)["id"]
    real_load = pipeline._load_active

    def slow_load(vid):                       # widen the window the live race fell into
        v = real_load(vid)
        time.sleep(0.05)
        return v

    monkeypatch.setattr(pipeline, "_load_active", slow_load)
    assert _race(4, lambda i: pipeline.on_call_status(ver_id, "in-progress")) == []
    ver = repo.get_verification(db, ver_id)
    assert [e["label"] for e in ver["events"]].count("Answered") == 1 and ver["step"] == "answered"
    rows = db.execute("SELECT data FROM audit_log WHERE subject_id=? AND event='call_status'", (iid,)).fetchall()
    assert len(rows) == 1


def test_simultaneous_completed_is_handled_once(db, twilio_env, monkeypatch):
    monkeypatch.setattr(pipeline, "COMPLETED_GRACE_S", 0)
    scheduled: list[str] = []
    monkeypatch.setattr(pipeline, "_after_completed", scheduled.append)
    iid = calling("02_acme_fraud")
    ver_id = latest(db, iid)["id"]
    assert _race(4, lambda i: pipeline.on_call_status(ver_id, "completed")) == []
    labels = [e["label"] for e in repo.get_verification(db, ver_id)["events"]]
    assert labels.count(pipeline.CALL_COMPLETED) == 1 and scheduled == [ver_id]


def test_concurrent_timeline_appends_lose_nothing(db, twilio_env):
    iid = calling("02_acme_fraud")
    ver_id = latest(db, iid)["id"]
    before = len(latest(db, iid)["events"])

    def add(i: int) -> None:
        c = dbm.connect()
        try:
            verifications.add_event(c, ver_id, f"event {i}")
        finally:
            c.close()

    assert _race(8, add) == []
    labels = [e["label"] for e in repo.get_verification(db, ver_id)["events"]]
    assert len(labels) == before + 8 and {f"event {i}" for i in range(8)} <= set(labels)
