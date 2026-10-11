"""PLAN.md §9.4: the phone never waits for the LLM (SC-001), and the slow path is bounded (SC-006)."""
from __future__ import annotations

import time

import pytest

from app import ai_mode, config, db as dbm, engine, executors, pipeline, repo
from tests.fakes import ANALYST, INTAKE, PAYMENTS, ScriptedModel, SlowModel, structured_turn, text_turn

NULL_EXTRACTION = {"vendor_name": None, "invoice_number": None, "amount": None, "due_date": None, "bank_name": None,
                   "routing_number": None, "account_number": None}
REPORT = {"headline": "h", "explanation": "e", "cited_flags": [], "recommended_next_step": "n"}


@pytest.fixture
def live_threads():
    ai_mode.set_ai_mode("live", record=False)
    executors.use_thread_executors()
    yield
    executors.wait_idle(20)


def _poll(iid: str, pred, timeout: float) -> tuple[dict, float]:
    t0 = time.perf_counter()
    while True:
        c = dbm.connect()
        try:
            inv = repo.get_invoice(c, iid)
        finally:
            c.close()
        if pred(inv):
            return inv, time.perf_counter() - t0
        if time.perf_counter() - t0 > timeout:
            raise AssertionError(f"timed out; last status {inv['status']}")
        time.sleep(0.02)


def test_fraud_rings_before_the_intake_agent_answers(db, live_threads, fake_models):
    disagree = {**NULL_EXTRACTION, "invoice_number": "INV-99999"}       # disagrees with the text value
    fake_models({INTAKE: lambda: SlowModel(2.0, [structured_turn(disagree)]),
                 ANALYST: lambda: ScriptedModel([structured_turn(REPORT)])})
    iid = pipeline.submit_invoice(engine.load_sample("02_acme_fraud"), source="sample", sample_name="02_acme_fraud")
    inv, elapsed = _poll(iid, lambda i: i["status"] in ("CALL_PENDING", "CALLING"), timeout=5)
    assert elapsed < 5.0                                                  # SC-001
    assert inv["extraction"]["llm_status"] == "pending"                   # scored before any model answered
    assert inv["risk"]["points"] == 160 and inv["risk"]["action"] == "CALLBACK"

    inv, _ = _poll(iid, lambda i: i["extraction"]["llm_status"] != "pending", timeout=10)
    assert inv["extraction"]["llm_status"] == "ok"
    codes = [(f["code"], f["points"]) for f in inv["risk"]["flags"]]
    assert ("EXTRACTION_MISMATCH", 0) in codes
    assert (inv["risk"]["points"], inv["risk"]["tier"], inv["risk"]["action"]) == (160, "RED", "CALLBACK")
    assert inv["extraction"]["invoice_number"]["value"] == "INV-20447"     # text wins


def test_unknown_vendor_waits_for_intake_but_is_bounded(db, live_threads, fake_models, monkeypatch):
    monkeypatch.setenv("TIMEOUT_INTAKE_S", "1")
    config.reload()
    fake_models({INTAKE: lambda: SlowModel(5.0, [structured_turn(NULL_EXTRACTION)]),
                 PAYMENTS: lambda: ScriptedModel([text_turn("Holding.")])})
    t0 = time.perf_counter()
    iid = pipeline.submit_invoice(engine.load_sample("05_unknown_vendor"), source="sample", sample_name="05_unknown_vendor")
    inv, _ = _poll(iid, lambda i: i["status"] == "HELD", timeout=config.S.timeout_intake_s + 5)
    assert time.perf_counter() - t0 < config.S.timeout_intake_s + 5    # SC-006
    assert inv["hold_reason"] == "UNKNOWN_VENDOR"
    assert (inv["risk"]["points"], inv["risk"]["action"]) == (60, "HOLD_MANUAL")
    assert inv["extraction"]["llm_status"] == "fallback" and inv["ai_fallback"] == 1
    _poll(iid, lambda i: i.get("memo") is not None, timeout=10)
