"""Run the engine on each sample with AI off and simulated verification
outcomes, and write PLAN.md §7.6-shaped JSON for the UI session.

    python scripts/export_fixtures.py [--out web/src/fixtures]

Output is deterministic (fixed clock and ids), so re-running produces
identical files. One scratch database is used for all scenarios in demo-story
order, so the vendors/payments/stats fixtures reflect the whole story.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("AI_MODE", "off")
os.environ.setdefault("DEMO_MODE", "1")
os.environ.setdefault("VOICE_MODE", "simulated")

from app import config, db, engine, ids, ledger, repo, seed, verifications  # noqa: E402
from app.state import HoldReason, Status, transition  # noqa: E402

SCENARIOS = ["acme_normal", "acme_fraud", "heartland_bank_change", "prairie_review", "unknown_vendor"]
SAMPLE_FOR = {
    "acme_normal": "01_acme_normal", "acme_fraud": "02_acme_fraud",
    "heartland_bank_change": "03_heartland_bank_change", "prairie_review": "04_prairie_review",
    "unknown_vendor": "05_unknown_vendor",
}


def _snap(conn: sqlite3.Connection, steps: list, iid: str, name: str) -> None:
    steps.append((name, repo.invoice_detail(conn, iid)))


def _start_call(conn, iid, *, source="simulated"):
    transition(iid, Status.CALLING, actor="demo", conn=conn)
    ver_id, _ = verifications.create(conn, iid, source=source, step="placed", first_event="Dialing")
    verifications.add_event(conn, ver_id, "Ringing", step="ringing")
    verifications.add_event(conn, ver_id, "Answered", step="answered")
    verifications.add_event(conn, ver_id, "Asked", "Did the vendor request this bank change?", step="asked")
    return ver_id


def run_scenario(conn: sqlite3.Connection, scenario: str) -> list[tuple[str, dict]]:
    steps: list[tuple[str, dict]] = []
    iid = engine.ingest_sample(SAMPLE_FOR[scenario], conn=conn)
    _snap(conn, steps, iid, "scored")

    if scenario == "acme_normal":
        ledger.release(iid, by="policy:auto", conn=conn)
        _snap(conn, steps, iid, "paid")

    elif scenario == "acme_fraud":
        ver = _start_call(conn, iid)
        _snap(conn, steps, iid, "calling")
        verifications.record_answer(conn, ver, speech="No, we never changed banks", confidence=0.93, det_label="NO",
                                    llm_label="DENIED", llm_rationale="Speaker explicitly denies any bank change.")
        verifications.add_event(conn, ver, "Answer", "\"No, we never changed banks\"")
        verifications.finalize(conn, ver, "DENIED", actor="demo", detail="Vendor denied the change")
        transition(iid, Status.HELD, hold_reason=HoldReason.DENIED_BY_VENDOR, actor="demo", conn=conn)
        repo.update_invoice(conn, iid, memo={"text": "Held: Acme Supply Co. said on the callback that they never changed banks. "
                                                     "The email came from a lookalike domain and asked for $48,750.00 to a new account.",
                                             "by": "fallback"})
        _snap(conn, steps, iid, "held")

    elif scenario == "heartland_bank_change":
        ver = _start_call(conn, iid)
        _snap(conn, steps, iid, "calling")
        verifications.record_answer(conn, ver, digits="1", det_label="YES")
        verifications.add_event(conn, ver, "Answer", "Pressed 1")
        verifications.add_event(conn, ver, "Last four", "Entered 4455", step="awaiting_last4")
        verifications.finalize(conn, ver, "CONFIRMED", last4_ok=1, actor="demo", detail="Confirmed by keypad, last four matched")
        transition(iid, Status.CONFIRMED, actor="demo", conn=conn)
        ledger.apply_vendor_bank_change(iid, ver, conn=conn)
        _snap(conn, steps, iid, "confirmed")
        ledger.release(iid, by="policy:auto", conn=conn)
        _snap(conn, steps, iid, "paid")

    elif scenario == "prairie_review":
        ledger.record_review(iid, "approve", "Annual support renewal; expected.", conn=conn)
        _snap(conn, steps, iid, "approved")
        ledger.release(iid, by="policy:auto", conn=conn)
        _snap(conn, steps, iid, "paid")

    elif scenario == "unknown_vendor":
        pass  # already HELD(UNKNOWN_VENDOR) at "scored"

    return steps


def health_fixture() -> dict:
    return {"db": True, "model": {"ok": False, "latency_ms": None, "checked_at": None},
            "twilio": {"configured": False}, "storage": {"ok": True}, "demo_mode": True, "ai_mode": "off",
            "deploy_label": config.S.deploy_label}


def main(out_dir: Path) -> dict:
    ids.set_deterministic("2026-10-10T15:00:00Z", 1)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["DB_PATH"] = str(Path(tmp) / "fixtures.db")
            config.reload()
            db.init_db()
            conn = db.connect()
            try:
                seed.reset_demo_data(conn)
                out_dir.mkdir(parents=True, exist_ok=True)
                index: dict[str, list[dict]] = {}
                for scenario in SCENARIOS:
                    steps = run_scenario(conn, scenario)
                    sdir = out_dir / scenario
                    sdir.mkdir(exist_ok=True)
                    index[scenario] = []
                    for n, (name, detail) in enumerate(steps, start=1):
                        fname = f"{n:02d}_{name}.json"
                        (sdir / fname).write_text(json.dumps(detail, indent=2, ensure_ascii=False) + "\n")
                        index[scenario].append({"step": name, "file": f"{scenario}/{fname}",
                                                "status": detail["status"], "hold_reason": detail["hold_reason"],
                                                "invoice_id": detail["id"]})
                (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
                (out_dir / "invoices_list.json").write_text(json.dumps(repo.list_invoices(conn), indent=2, ensure_ascii=False) + "\n")
                (out_dir / "vendors.json").write_text(json.dumps(repo.vendors_view(conn), indent=2, ensure_ascii=False) + "\n")
                (out_dir / "payments.json").write_text(json.dumps(repo.payments_view(conn), indent=2, ensure_ascii=False) + "\n")
                (out_dir / "stats.json").write_text(json.dumps(repo.stats_view(conn), indent=2) + "\n")
                (out_dir / "health.json").write_text(json.dumps(health_fixture(), indent=2) + "\n")
                from app import audit
                ok, broken = audit.verify(conn)
                (out_dir / "audit.json").write_text(json.dumps(
                    {"entries": [{k: e[k] for k in ("seq", "ts", "subject_id", "actor", "event", "summary", "hash_short")}
                                 for e in audit.list_entries(limit=200, conn=conn)],
                     "chain_ok": ok, "broken_at": broken}, indent=2, ensure_ascii=False) + "\n")
                return index
            finally:
                conn.close()
    finally:
        ids.set_deterministic(None)
        os.environ.pop("DB_PATH", None)
        config.reload()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "web" / "src" / "fixtures"))
    args = ap.parse_args()
    idx = main(Path(args.out))
    for scenario, steps in idx.items():
        print(f"{scenario}: " + " → ".join(f"{s['step']}({s['status']})" for s in steps))
    print(f"wrote fixtures to {args.out}")
