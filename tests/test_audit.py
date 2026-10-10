"""PLAN.md §13.2 hash chain and §17.1 audit vectors."""
from __future__ import annotations

import json
import threading

import pytest

from app import audit


def test_append_five_and_verify(db):
    for i in range(5):
        audit.append("inv_a", "system", "call_status", {"i": i}, conn=db)
    assert audit.verify(db) == (True, None)
    rows = db.execute("SELECT seq, prev_hash, hash FROM audit_log ORDER BY seq").fetchall()
    assert [r[0] for r in rows] == [1, 2, 3, 4, 5]
    assert rows[0][1] == "0" * 64
    for prev, cur in zip(rows, rows[1:], strict=False):
        assert cur[1] == prev[2]
    assert len({r[2] for r in rows}) == 5


def test_tampered_row_is_detected_at_its_seq(db):
    for i in range(5):
        audit.append("inv_a", "system", "call_status", {"i": i}, conn=db)
    db.execute("UPDATE audit_log SET data=? WHERE seq=3", (json.dumps({"i": 99}),))
    assert audit.verify(db) == (False, 3)


def test_tampered_hash_or_gap_is_detected(db):
    for i in range(4):
        audit.append("inv_a", "system", "call_status", {"i": i}, conn=db)
    db.execute("UPDATE audit_log SET hash='deadbeef' WHERE seq=2")
    assert audit.verify(db) == (False, 2)
    db.execute("DELETE FROM audit_log WHERE seq=2")
    assert audit.verify(db) == (False, 3)


def test_empty_chain_verifies(db):
    assert audit.verify(db) == (True, None)


def test_concurrent_appends_are_consecutive_and_verify(db):
    errors: list[Exception] = []

    def worker(n: int):
        try:
            for _ in range(5):
                audit.append("inv_c", "system", "call_status", {"n": n})
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    seqs = [r[0] for r in db.execute("SELECT seq FROM audit_log ORDER BY seq").fetchall()]
    assert seqs == list(range(1, 101))
    assert audit.verify(db) == (True, None)


def test_data_is_masked_and_names_validated(db):
    audit.append("inv_m", "twilio", "answer_received",
                 {"account": "7730019942", "phone": "+18165550199", "routing": "061100059"}, conn=db)
    data = json.loads(db.execute("SELECT data FROM audit_log WHERE subject_id='inv_m'").fetchone()[0])
    assert data == {"account": "••••9942", "phone": "•••-•••-0199", "routing": "061100059"}
    with pytest.raises(ValueError):
        audit.append("inv_m", "hacker", "answer_received", {}, conn=db)
    with pytest.raises(ValueError):
        audit.append("inv_m", "twilio", "made_up", {}, conn=db)


def test_list_entries_shape_and_summary(db):
    audit.append("inv_l", "policy", "risk_scored", {"points": 160, "tier": "RED", "action": "CALLBACK"}, conn=db)
    audit.append("inv_l", "policy", "status_changed", {"from": "SCORED", "to": "CALL_PENDING", "hold_reason": None}, conn=db)
    audit.append("inv_other", "system", "invoice_received", {}, conn=db)
    entries = audit.list_entries("inv_l", conn=db)
    assert [e["seq"] for e in entries] == [1, 2]
    assert entries[0]["summary"] == "160 points, RED, CALLBACK"
    assert entries[1]["summary"] == "SCORED → CALL_PENDING"
    assert len(entries[0]["hash_short"]) == 6
    assert set(entries[0]) >= {"seq", "ts", "actor", "event", "summary", "hash_short", "data"}
    assert [e["seq"] for e in audit.list_entries(limit=2, conn=db)] == [2, 3]


def test_append_joins_open_transaction_and_rolls_back_with_it(db):
    from app.db import tx
    with pytest.raises(RuntimeError):
        with tx(db):
            audit.append("inv_r", "system", "invoice_received", {}, conn=db)
            raise RuntimeError("abort")
    assert db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 0
