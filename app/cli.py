"""Developer entry point for the core engine (spec 003 only; not an HTTP route).

    python -m app.cli seed
    python -m app.cli score 02_acme_fraud
    python -m app.cli list
    python -m app.cli detail inv_...
    python -m app.cli audit-verify
    python -m app.cli reset
"""
from __future__ import annotations

import argparse
import json
import sys

from app import audit, db, engine, repo, seed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("reset")
    sub.add_parser("list")
    sub.add_parser("audit-verify")
    p = sub.add_parser("score")
    p.add_argument("sample")
    d = sub.add_parser("detail")
    d.add_argument("invoice_id")
    args = ap.parse_args(argv)

    db.init_db()
    conn = db.connect()
    try:
        if args.cmd == "seed":
            with db.tx(conn):
                seed.seed_vendors(conn)
                seed.seed_history(conn)
            print("seeded")
        elif args.cmd == "reset":
            seed.reset_demo_data(conn)
            print("reset; audit chain restarted")
        elif args.cmd == "score":
            iid = engine.ingest_sample(args.sample, conn=conn)
            inv = repo.get_invoice(conn, iid)
            risk = repo.get_risk(conn, iid)
            for f in risk.flags:
                print(f"  {f.code:<22} +{f.points:<3} {f.title}")
            print(f"{iid}: {risk.points} points, {risk.tier}, {risk.action} → {inv['status']}"
                  + (f" ({inv['hold_reason']})" if inv.get("hold_reason") else ""))
        elif args.cmd == "list":
            for row in repo.list_invoices(conn):
                print(f"{row['id']}  {row['status']:<15} {str(row['tier']):<7} {str(row['points']):>4}  "
                      f"{row['vendor_name']}  {row['amount_display']}")
        elif args.cmd == "detail":
            print(json.dumps(repo.invoice_detail(conn, args.invoice_id), indent=2, ensure_ascii=False))
        elif args.cmd == "audit-verify":
            ok, broken = audit.verify(conn)
            n = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            print(f"chain_ok={ok} broken_at={broken} entries={n}")
            return 0 if ok else 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
