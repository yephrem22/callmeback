"""AI-off orchestration for one invoice (PLAN.md §5 steps 1–3, §9, §10):
RECEIVED → EXTRACTED → SCORED → routed. Spec 005's pipeline wraps this with
the fast path and the agents; nothing here calls a model or the network."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app import audit, config, db, repo
from app.ids import new_id
from app.intake import eml, merge, regex_extract
from app.models import RiskResult
from app.policy import engine as policy
from app.state import HoldReason, Status, transition

SAMPLES_DIR = config.REPO_ROOT / "samples"


def sample_names() -> list[str]:
    return [m["name"] for m in json.loads((SAMPLES_DIR / "manifest.json").read_text())]


def ingest_sample(name: str, conn: sqlite3.Connection | None = None) -> str:
    path = SAMPLES_DIR / f"{name}.eml"
    if not path.exists() or name not in sample_names():
        raise FileNotFoundError(f"unknown sample {name}")
    return _ingest(path.read_bytes(), source="sample", sample_name=name, conn=conn)


def ingest_upload(raw: bytes, conn: sqlite3.Connection | None = None) -> str:
    return _ingest(raw, source="upload", sample_name=None, conn=conn)


def _ingest(raw: bytes, *, source: str, sample_name: str | None, conn: sqlite3.Connection | None) -> str:
    parsed = eml.parse(raw)          # raises ValueError → nothing is stored
    close = conn is None
    c = conn or db.connect()
    try:
        invoice_id = new_id("inv_")
        with db.tx(c):
            repo.insert_invoice(
                c, id=invoice_id, source=source, sample_name=sample_name, raw_sha256=parsed.raw_sha256,
                from_name=parsed.from_name, from_email=parsed.from_email, from_domain=parsed.from_domain,
                reply_to=parsed.reply_to or None, reply_to_domain=parsed.reply_to_domain or None,
                subject=parsed.subject, received_at=parsed.received_at, body_text=parsed.body_text,
                status=Status.RECEIVED.value,
            )
            audit.append(invoice_id, "system", "invoice_received",
                         {"source": source, "sample_name": sample_name, "from_email": parsed.from_email,
                          "subject": parsed.subject, "sha256": parsed.raw_sha256}, conn=c)
        score_invoice(invoice_id, parsed, conn=c)
        return invoice_id
    finally:
        if close:
            c.close()


def score_invoice(invoice_id: str, parsed: eml.ParsedEmail, conn: sqlite3.Connection) -> RiskResult:
    """Extract (text only), resolve, score and route. Idempotent for a RECEIVED invoice."""
    rx = regex_extract.extract(parsed.body_text)
    extraction = merge.merge(rx, None, parsed.body_text, parsed.from_name, llm_status="fallback")
    mismatch = merge.has_mismatch(extraction, rx)

    with db.tx(conn):
        repo.update_invoice(conn, invoice_id, extraction=extraction.model_dump())
        transition(invoice_id, Status.EXTRACTED, actor="system", conn=conn)
        audit.append(invoice_id, "system", "extraction_done",
                     {"fields": {k: getattr(extraction, k).value for k in
                                 ("vendor_name", "invoice_number", "amount", "due_date", "bank_name",
                                  "routing_number", "account_number")},
                      "llm_status": extraction.llm_status}, conn=conn)
        if mismatch:
            audit.append(invoice_id, "system", "extraction_mismatch",
                         {"all_routing": rx.all_routing, "all_account": rx.all_account}, conn=conn)

    res = policy.resolve_vendor(conn, parsed.from_domain, extraction.vendor_name.value)
    risk = policy.score(conn, parsed, extraction, res, extraction_mismatch=mismatch)

    with db.tx(conn):
        repo.update_invoice(conn, invoice_id, vendor_id=res.vendor["id"] if res.vendor else None)
        audit.append(invoice_id, "policy", "vendor_resolved",
                     {"vendor_id": res.vendor["id"] if res.vendor else None,
                      "vendor_name": res.vendor["name"] if res.vendor else None,
                      "sender_status": res.sender_status, "from_domain": parsed.from_domain,
                      "known_domain": res.known_domain}, conn=conn)
        repo.update_invoice(conn, invoice_id, risk=risk.model_dump())
        transition(invoice_id, Status.SCORED, actor="policy", conn=conn)
        audit.append(invoice_id, "policy", "risk_scored",
                     {"points": risk.points, "tier": risk.tier, "action": risk.action,
                      "flags": [{"code": f.code, "points": f.points} for f in risk.flags],
                      "policy_version": risk.policy_version}, conn=conn)
        _route(invoice_id, risk, conn)
    return risk


def _route(invoice_id: str, risk: RiskResult, conn: sqlite3.Connection) -> None:
    if risk.action == "AUTO_RELEASE":
        transition(invoice_id, Status.AUTO_APPROVED, actor="policy", conn=conn)
    elif risk.action == "REVIEW":
        transition(invoice_id, Status.NEEDS_REVIEW, actor="policy", conn=conn)
    elif risk.action == "CALLBACK":
        transition(invoice_id, Status.CALL_PENDING, actor="policy", conn=conn)
    elif risk.action == "HOLD_MANUAL":
        transition(invoice_id, Status.HELD, hold_reason=HoldReason.UNKNOWN_VENDOR, actor="policy",
                   detail={"reason": "no vendor record, so there is no trusted number to call"}, conn=conn)
    else:  # pragma: no cover
        raise ValueError(f"unknown action {risk.action}")


def load_sample(name: str) -> bytes:
    return Path(SAMPLES_DIR / f"{name}.eml").read_bytes()
