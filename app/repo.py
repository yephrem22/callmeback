"""Typed DB helpers. Phase 1 subset: vendors, history, invoices.
Later phases add verifications, payments, bank history and invoice_detail()."""
from __future__ import annotations

import json
import sqlite3
import statistics
from typing import Any

from app.ids import now_iso

JSON_COLUMNS = {"domains", "extraction", "risk", "analyst", "memo", "review", "events",
                "account_ref", "signals", "callback_target", "source_refs"}


_COLUMNS: dict[str, frozenset[str]] = {}


def columns(conn: sqlite3.Connection, table: str) -> frozenset[str]:
    """Column allowlist from the schema, cached per table; keyword arguments
    are checked against it before they are interpolated into SQL."""
    if table not in _COLUMNS:
        _COLUMNS[table] = frozenset(r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall())
    return _COLUMNS[table]


def _check_columns(conn: sqlite3.Connection, table: str, keys: Any) -> None:
    bad = set(keys) - columns(conn, table)
    if bad:
        raise ValueError(f"unknown {table} column(s): {sorted(bad)}")


def _encode(key: str, value: Any) -> Any:
    if key in JSON_COLUMNS and not isinstance(value, (str, type(None))):
        return json.dumps(value, sort_keys=True)
    return value


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for k in list(d):
        if k in JSON_COLUMNS and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


# ---- vendors -----------------------------------------------------------------

def get_vendor(conn: sqlite3.Connection, vendor_id: str) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM vendors WHERE id=?", (vendor_id,)).fetchone())


def list_vendors(conn: sqlite3.Connection) -> list[dict]:
    return [row_to_dict(r) for r in conn.execute("SELECT * FROM vendors ORDER BY name").fetchall()]


def vendor_history(conn: sqlite3.Connection, vendor_id: str, limit: int = 6) -> list[dict]:
    """The vendor's last `limit` paid invoices, oldest first (PLAN.md §7.6)."""
    rows = conn.execute(
        "SELECT invoice_number, amount_cents, paid_on FROM invoice_history "
        "WHERE vendor_id=? ORDER BY paid_on DESC, id DESC LIMIT ?",
        (vendor_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def vendor_history_count(conn: sqlite3.Connection, vendor_id: str) -> int:
    return conn.execute("SELECT COUNT(*) FROM invoice_history WHERE vendor_id=?", (vendor_id,)).fetchone()[0]


def vendor_median_cents(conn: sqlite3.Connection, vendor_id: str) -> int | None:
    amounts = [r[0] for r in conn.execute(
        "SELECT amount_cents FROM invoice_history WHERE vendor_id=?", (vendor_id,)).fetchall()]
    if not amounts:
        return None
    return int(round(statistics.median(amounts)))


# ---- invoices ----------------------------------------------------------------

def insert_invoice(conn: sqlite3.Connection, **cols: Any) -> str:
    ts = now_iso()
    cols.setdefault("created_at", ts)
    cols.setdefault("updated_at", ts)
    cols.setdefault("status", "RECEIVED")
    cols.setdefault("version", 0)
    cols.setdefault("ai_fallback", 0)
    keys = list(cols)
    _check_columns(conn, "invoices", keys)
    conn.execute(
        f"INSERT INTO invoices ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        [_encode(k, cols[k]) for k in keys],
    )
    return cols["id"]


def get_invoice(conn: sqlite3.Connection, invoice_id: str) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone())


def update_invoice(conn: sqlite3.Connection, invoice_id: str, **cols: Any) -> None:
    if not cols:
        return
    cols["updated_at"] = now_iso()
    _check_columns(conn, "invoices", cols)
    sets = ", ".join(f"{k}=?" for k in cols)
    conn.execute(f"UPDATE invoices SET {sets} WHERE id=?",
                 [_encode(k, v) for k, v in cols.items()] + [invoice_id])


def get_risk(conn: sqlite3.Connection, invoice_id: str):
    from app.models import RiskResult

    inv = get_invoice(conn, invoice_id)
    if not inv or not inv.get("risk"):
        return None
    return RiskResult.model_validate(inv["risk"])


def list_invoices(conn: sqlite3.Connection) -> list[dict]:
    """Queue rows, newest first (PLAN.md §7.6 GET /api/invoices)."""
    out = []
    rows = conn.execute(
        "SELECT i.*, v.name AS _vendor_name FROM invoices i LEFT JOIN vendors v ON v.id = i.vendor_id "
        "ORDER BY i.created_at DESC, i.rowid DESC").fetchall()
    for r in rows:
        inv = row_to_dict(r)
        risk = inv.get("risk") or {}
        ext = inv.get("extraction") or {}
        amount_cents = risk.get("amount_cents")
        vendor_name = inv.pop("_vendor_name", None)
        if not vendor_name:
            vendor_name = ((ext.get("vendor_name") or {}).get("value")) or inv.get("from_name")
        out.append({
            "id": inv["id"],
            "created_at": inv["created_at"],
            "vendor_name": vendor_name,
            "amount_display": f"${amount_cents / 100:,.2f}" if amount_cents is not None else None,
            "tier": risk.get("tier"),
            "points": risk.get("points"),
            "status": inv["status"],
            "hold_reason": inv.get("hold_reason"),
            "source": inv["source"],
        })
    return out


# ---- verifications -------------------------------------------------------------

def insert_verification(conn: sqlite3.Connection, **cols: Any) -> str:
    ts = now_iso()
    cols.setdefault("created_at", ts)
    cols.setdefault("updated_at", ts)
    cols.setdefault("events", [])
    cols.setdefault("attempts", 0)
    cols.setdefault("step", "created")
    keys = list(cols)
    _check_columns(conn, "verifications", keys)
    conn.execute(
        f"INSERT INTO verifications ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        [_encode(k, cols[k]) for k in keys],
    )
    return cols["id"]


def get_verification(conn: sqlite3.Connection, ver_id: str) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM verifications WHERE id=?", (ver_id,)).fetchone())


def latest_verification(conn: sqlite3.Connection, subject_id: str) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM verifications WHERE subject_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
        (subject_id,)).fetchone())


def update_verification(conn: sqlite3.Connection, ver_id: str, **cols: Any) -> None:
    if not cols:
        return
    cols["updated_at"] = now_iso()
    _check_columns(conn, "verifications", cols)
    sets = ", ".join(f"{k}=?" for k in cols)
    conn.execute(f"UPDATE verifications SET {sets} WHERE id=?",
                 [_encode(k, v) for k, v in cols.items()] + [ver_id])


# ---- payments ------------------------------------------------------------------

def insert_payment(conn: sqlite3.Connection, **cols: Any) -> str:
    cols.setdefault("released_at", now_iso())
    cols.setdefault("method", "ACH-CCD")
    keys = list(cols)
    _check_columns(conn, "payments", keys)
    conn.execute(
        f"INSERT INTO payments ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        [cols[k] for k in keys],
    )
    return cols["id"]


def get_payment(conn: sqlite3.Connection, invoice_id: str) -> dict | None:
    return row_to_dict(conn.execute("SELECT * FROM payments WHERE invoice_id=?", (invoice_id,)).fetchone())


def list_payments(conn: sqlite3.Connection) -> list[dict]:
    return [row_to_dict(r) for r in conn.execute("SELECT * FROM payments ORDER BY released_at DESC, rowid DESC").fetchall()]


# ---- vendor bank history -------------------------------------------------------

def insert_bank_history(conn: sqlite3.Connection, **cols: Any) -> None:
    cols.setdefault("changed_at", now_iso())
    keys = list(cols)
    _check_columns(conn, "vendor_bank_history", keys)
    conn.execute(
        f"INSERT INTO vendor_bank_history ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)})",
        [cols[k] for k in keys],
    )


def vendor_bank_history(conn: sqlite3.Connection, vendor_id: str) -> list[dict]:
    return [row_to_dict(r) for r in conn.execute(
        "SELECT * FROM vendor_bank_history WHERE vendor_id=? ORDER BY changed_at, id", (vendor_id,)).fetchall()]


def bank_history_for_verification(conn: sqlite3.Connection, verification_id: str) -> dict | None:
    return row_to_dict(conn.execute(
        "SELECT * FROM vendor_bank_history WHERE verification_id=?", (verification_id,)).fetchone())


def update_vendor_bank(conn: sqlite3.Connection, vendor_id: str, bank_name: str | None,
                       routing: str, account: str) -> None:
    conn.execute("UPDATE vendors SET bank_name=?, routing=?, account=?, updated_at=? WHERE id=?",
                 (bank_name, routing, account, now_iso(), vendor_id))
