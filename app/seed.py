"""Vendor master and invoice history (PLAN.md §8.1, §8.2) and the demo reset
(PLAN.md §7.6). All names are fictional."""
from __future__ import annotations

import json
import sqlite3

from app import audit, config, db
from app.ids import now_iso

VENDORS = [
    # id, name, domains, bank_name, routing, account
    ("ven_acme", "Acme Supply Co.", ["acme-supply.com"], "Plains Federal Bank", "123456780", "4421984821"),
    ("ven_heartland", "Heartland Logistics LLC", ["heartland-logistics.com"], "River City Bank", "102030402", "5512003377"),
    ("ven_prairie", "Prairie Cloud Hosting", ["prairiecloud.io"], "Midland Trust Bank", "301112228", "8800142201"),
]

# Amounts in cents; paid one month apart, April to September 2026 (medians 12,020 / 3,995 / 2,499).
HISTORY = {
    "ven_acme": [("INV-20301", 1182000), ("INV-20322", 1204000), ("INV-20355", 1196000),
                 ("INV-20381", 1231000), ("INV-20398", 1200000), ("INV-20412", 1215000)],
    "ven_heartland": [("HL-8701", 395000), ("HL-8724", 401000), ("HL-8740", 398000),
                      ("HL-8763", 406000), ("HL-8781", 410000), ("HL-8795", 390000)],
    "ven_prairie": [(f"PCH-110{i}", 249900) for i in range(1, 7)],
}

PAID_ON = ["2026-04-15", "2026-05-15", "2026-06-15", "2026-07-15", "2026-08-15", "2026-09-15"]


def seed_vendors(conn: sqlite3.Connection) -> None:
    ts = now_iso()
    for vid, name, domains, bank, routing, account in VENDORS:
        conn.execute(
            "INSERT OR REPLACE INTO vendors (id, name, domains, phone_on_file, bank_name, routing, account, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (vid, name, json.dumps(domains), config.S.demo_vendor_phone, bank, routing, account, ts),
        )


def seed_history(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM invoice_history")
    for vid, rows in HISTORY.items():
        for (number, cents), paid_on in zip(rows, PAID_ON, strict=True):
            conn.execute(
                "INSERT INTO invoice_history (vendor_id, invoice_number, amount_cents, paid_on) VALUES (?,?,?,?)",
                (vid, number, cents, paid_on),
            )


def reset_demo_data(conn: sqlite3.Connection, include_change_cases: bool = False) -> None:
    """Wipe invoices, verifications, payments, traces and audit; reseed vendors
    and history (undoing any vendor bank update); restart the audit chain with
    a demo_reset genesis event. Keeps DevRev change cases unless asked."""
    with db.tx(conn):
        for table in ("payments", "agent_traces", "vendor_bank_history", "invoices", "audit_log"):
            conn.execute(f"DELETE FROM {table}")
        if include_change_cases:
            conn.execute("DELETE FROM verifications")
            conn.execute("DELETE FROM change_cases")
        else:
            conn.execute("DELETE FROM verifications WHERE kind='invoice'")
        seed_vendors(conn)
        seed_history(conn)
        audit.append(None, "demo", "demo_reset", {"include_change_cases": include_change_cases}, conn=conn)


def main() -> None:
    db.init_db()
    conn = db.connect()
    try:
        with db.tx(conn):
            seed_vendors(conn)
            seed_history(conn)
    finally:
        conn.close()
    print(f"seeded {config.S.db_path}")


if __name__ == "__main__":
    main()
