"""The dashboard API (PLAN.md §7.6; spec US4). Plain `def` handlers run in FastAPI's threadpool
(research R7); background work goes through app/executors.py via the pipeline.

Errors: IllegalTransition / PolicyViolation / RedteamRefused / SimulateNotAllowed → 409,
ValueError → 400, unknown ids → 404. Demo routes answer 404 when DEMO_MODE is off.
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app import ai_mode, audit, config, db, engine, health, ledger, pipeline, repo, seed
from app.agents.redteam import RedteamRefused, redteam
from app.intake.eml import MAX_BYTES
from app.ledger import PolicyViolation
from app.masking import mask_phone, masked
from app.state import IllegalTransition, Status

router = APIRouter(prefix="/api")

CASE_JSON = ("account_ref", "signals", "source_refs", "callback_target")
AUDIT_KEYS = ("seq", "ts", "subject_id", "actor", "event", "summary", "hash_short")


class FromSample(BaseModel):
    name: str


class Review(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = ""


class Reset(BaseModel):
    include_change_cases: bool = False


class Simulate(BaseModel):
    subject_id: str
    answer: Literal["yes", "no"]
    last4: str | None = None


class AiMode(BaseModel):
    mode: Literal["live", "off"]


def _conflict(e: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(e))


def _require_demo() -> None:
    if not config.S.demo_mode:
        raise HTTPException(status_code=404, detail="Not Found")


def _require_invoice(invoice_id: str) -> dict:
    c = db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
    finally:
        c.close()
    if inv is None:
        raise HTTPException(status_code=404, detail="unknown invoice")
    return inv


# ---- health and samples ------------------------------------------------------

@router.get("/health")
def get_health() -> dict:
    return health.health()


@router.get("/samples")
def get_samples() -> list[dict]:
    manifest = json.loads((engine.SAMPLES_DIR / "manifest.json").read_text())
    return [{"name": m["name"], "title": m["title"], "description": m["description"]} for m in manifest]


# ---- invoices ----------------------------------------------------------------

@router.post("/invoices/from-sample")
def from_sample(body: FromSample) -> dict:
    if body.name not in engine.sample_names():
        raise HTTPException(status_code=404, detail=f"unknown sample {body.name}")
    return {"id": pipeline.submit_invoice(engine.load_sample(body.name), source="sample", sample_name=body.name)}


@router.post("/invoices/upload")
def upload(file: UploadFile = File(...)) -> dict:
    if not (file.filename or "").lower().endswith(".eml"):
        raise HTTPException(status_code=400, detail="upload a .eml file")
    raw = file.file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="the file is larger than 1 MB")
    try:
        return {"id": pipeline.submit_invoice(raw, source="upload", sample_name=None)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/invoices")
def list_invoices() -> list[dict]:
    c = db.connect()
    try:
        return repo.list_invoices(c)
    finally:
        c.close()


@router.get("/invoices/{invoice_id}")
def invoice_detail(invoice_id: str) -> dict:
    c = db.connect()
    try:
        d = repo.invoice_detail(c, invoice_id)
    finally:
        c.close()
    if d is None:
        raise HTTPException(status_code=404, detail="unknown invoice")
    return d


@router.post("/invoices/{invoice_id}/review")
def review(invoice_id: str, body: Review) -> dict:
    inv = _require_invoice(invoice_id)
    if inv["status"] != Status.NEEDS_REVIEW:
        raise HTTPException(status_code=409, detail=f"review is only possible in NEEDS_REVIEW (the invoice is {inv['status']})")
    try:
        ledger.record_review(invoice_id, body.decision, body.note)
    except (IllegalTransition, PolicyViolation) as e:
        raise _conflict(e) from e
    pipeline.run_payments_agent(invoice_id)          # approve → release; reject → HELD, memo only (FR-006)
    return {"ok": True}


@router.post("/invoices/{invoice_id}/retry-callback")
def retry_callback(invoice_id: str) -> dict:
    _require_invoice(invoice_id)
    try:
        return {"verification_id": pipeline.retry_callback(invoice_id)}
    except IllegalTransition as e:
        raise _conflict(e) from e


@router.post("/invoices/{invoice_id}/redteam")
def run_redteam(invoice_id: str) -> dict:
    inv = _require_invoice(invoice_id)
    if not inv.get("risk"):
        raise HTTPException(status_code=409, detail="the invoice has not been scored yet")
    try:
        return redteam(invoice_id)
    except RedteamRefused as e:
        raise _conflict(e) from e


# ---- ledger views ------------------------------------------------------------

@router.get("/audit")
def get_audit(subject_id: str | None = None) -> dict:
    c = db.connect()
    try:
        entries = audit.list_entries(subject_id, conn=c)
        ok, broken_at = audit.verify(c)
    finally:
        c.close()
    return {"entries": [masked({k: e[k] for k in AUDIT_KEYS}) for e in entries], "chain_ok": ok, "broken_at": broken_at}


@router.get("/payments")
def get_payments() -> dict:
    c = db.connect()
    try:
        return repo.payments_view(c)
    finally:
        c.close()


@router.get("/stats")
def get_stats() -> dict:
    c = db.connect()
    try:
        return repo.stats_view(c)
    finally:
        c.close()


@router.get("/vendors")
def get_vendors() -> list[dict]:
    c = db.connect()
    try:
        return repo.vendors_view(c)
    finally:
        c.close()


# ---- change cases (DevRev tab) ----------------------------------------------

def _case_view(c, row) -> dict:
    case = dict(row)
    for k in CASE_JSON:
        if case.get(k):
            try:
                case[k] = json.loads(case[k])
            except (TypeError, ValueError):
                pass
    ver = repo.latest_verification(c, case["id"])
    case["verification"] = None if ver is None else {
        "id": ver["id"], "source": ver.get("source"), "step": ver.get("step"),
        "phone_masked": mask_phone(ver.get("phone_called")), "events": ver.get("events") or [],
        "final_label": ver.get("final_label"),
    }
    return masked(case)


@router.get("/change-cases")
def list_change_cases() -> list[dict]:
    c = db.connect()
    try:
        rows = c.execute("SELECT * FROM change_cases ORDER BY created_at DESC, rowid DESC").fetchall()
        return [_case_view(c, r) for r in rows]
    finally:
        c.close()


@router.get("/change-cases/{case_id}")
def get_change_case(case_id: str) -> dict:
    c = db.connect()
    try:
        row = c.execute("SELECT * FROM change_cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="unknown change case")
        return _case_view(c, row)
    finally:
        c.close()


# ---- demo controls (DEMO_MODE only) ------------------------------------------

@router.post("/demo/reset")
def demo_reset(body: Reset | None = None) -> dict:
    _require_demo()
    c = db.connect()
    try:
        seed.reset_demo_data(c, include_change_cases=bool(body and body.include_change_cases))
    finally:
        c.close()
    ai_mode.reset_override()
    health.reset_cache()
    return {"ok": True}


@router.post("/demo/simulate-answer")
def simulate_answer(body: Simulate) -> dict:
    _require_demo()
    _require_invoice(body.subject_id)
    try:
        pipeline.simulate_answer(body.subject_id, body.answer, body.last4)
    except (pipeline.SimulateNotAllowed, IllegalTransition) as e:
        raise _conflict(e) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


@router.post("/demo/ai-mode")
def set_ai_mode(body: AiMode) -> dict:
    _require_demo()
    return {"mode": ai_mode.set_ai_mode(body.mode)}
