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


# ---- views for the API and the fixtures (PLAN.md §7.6) --------------------------

def _mask_acct(a: str | None) -> str | None:
    return ("••••" + a[-4:]) if a else None


def _mask_phone(p: str | None) -> str | None:
    digits = "".join(ch for ch in (p or "") if ch.isdigit())
    return ("•••-•••-" + digits[-4:]) if digits else None


def vendor_view(conn: sqlite3.Connection, vendor: dict) -> dict:
    return {
        "id": vendor["id"], "name": vendor["name"], "domains": vendor["domains"],
        "phone_masked": _mask_phone(vendor["phone_on_file"]),
        "bank_masked": f"{vendor['bank_name']} {_mask_acct(vendor['account'])}",
        "history": vendor_history(conn, vendor["id"]),
        "median_cents": vendor_median_cents(conn, vendor["id"]),
    }


def vendors_view(conn: sqlite3.Connection) -> list[dict]:
    out = []
    for v in list_vendors(conn):
        d = vendor_view(conn, v)
        d["routing"] = v["routing"]
        d["bank_name"] = v["bank_name"]
        d["account_masked"] = _mask_acct(v["account"])
        d["bank_history"] = [{
            "old_bank_name": h["old_bank_name"], "old_routing": h["old_routing"],
            "old_account_masked": _mask_acct(h["old_account"]),
            "new_bank_name": h["new_bank_name"], "new_routing": h["new_routing"],
            "new_account_masked": _mask_acct(h["new_account"]),
            "invoice_id": h["invoice_id"], "verification_id": h["verification_id"], "changed_at": h["changed_at"],
        } for h in vendor_bank_history(conn, v["id"])]
        out.append(d)
    return out


def payment_view(p: dict | None) -> dict | None:
    if not p:
        return None
    return {"id": p["id"], "invoice_id": p["invoice_id"], "amount_cents": p["amount_cents"],
            "bank_name": p["bank_name"], "routing": p["routing"], "account_masked": _mask_acct(p["account"]),
            "method": p["method"], "effective_date": p["effective_date"], "released_at": p["released_at"],
            "released_by": p["released_by"]}


def payments_view(conn: sqlite3.Connection) -> dict:
    held = []
    for inv in list_invoices(conn):
        if inv["status"] == "HELD":
            full = get_invoice(conn, inv["id"])
            held.append({"id": inv["id"], "vendor_name": inv["vendor_name"],
                         "amount_cents": (full.get("risk") or {}).get("amount_cents"),
                         "hold_reason": inv["hold_reason"], "created_at": inv["created_at"]})
    return {"payments": [payment_view(p) for p in list_payments(conn)], "held": held}


def stats_view(conn: sqlite3.Connection) -> dict:
    from datetime import datetime

    released = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM payments").fetchone()[0]
    held_cents = 0
    decision_secs: list[float] = []
    n = 0
    for r in conn.execute("SELECT id, status, risk, created_at, updated_at FROM invoices").fetchall():
        n += 1
        inv = row_to_dict(r)
        risk = inv.get("risk") or {}
        if inv["status"] == "HELD":
            held_cents += risk.get("amount_cents") or 0
        if inv["status"] in ("RELEASED", "HELD", "FAILED"):
            try:
                a = datetime.fromisoformat(inv["created_at"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(inv["updated_at"].replace("Z", "+00:00"))
                decision_secs.append((b - a).total_seconds())
            except (ValueError, AttributeError):
                pass
    calls = conn.execute("SELECT COUNT(*) FROM verifications WHERE kind='invoice'").fetchone()[0]
    median = statistics.median(decision_secs) if decision_secs else None
    return {"released_cents": released, "held_cents": held_cents, "invoices": n, "calls_placed": calls,
            "median_decision_seconds": round(median, 1) if median is not None else None}


def list_traces(conn: sqlite3.Connection, subject_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT ts, agent, run_id, kind, name, summary, duration_ms FROM agent_traces WHERE subject_id=? ORDER BY id",
        (subject_id,)).fetchall()]


def invoice_detail(conn: sqlite3.Connection, invoice_id: str) -> dict | None:
    """The PLAN.md §7.6 InvoiceDetail shape. The UI depends on these exact keys;
    spec 005's GET /api/invoices/{id} and the fixtures exporter both call this."""
    from app import audit, config, ledger
    from app.models import RiskResult
    from app.policy.engine import amount_ratio
    from core.checks import lookalike_diff

    inv = get_invoice(conn, invoice_id)
    if inv is None:
        return None
    status = inv["status"]
    risk_raw = inv.get("risk")
    risk = RiskResult.model_validate(risk_raw) if risk_raw else None
    ext = inv.get("extraction") or {}
    vendor = get_vendor(conn, inv["vendor_id"]) if inv.get("vendor_id") else None
    ver = latest_verification(conn, invoice_id)
    pay = get_payment(conn, invoice_id)

    field_names = ("vendor_name", "invoice_number", "amount", "due_date", "bank_name", "routing_number", "account_number")
    fields = {}
    for name in field_names:
        f = ext.get(name) or {"value": None, "source": "none", "mismatch": False}
        value = f.get("value")
        if name == "account_number" and value:
            value = _mask_acct(value)
        fields[name] = {"value": value, "source": f.get("source", "none"), "mismatch": bool(f.get("mismatch"))}

    lookalike = None
    risk_view = None
    if risk:
        if risk.sender_status == "LOOKALIKE":
            flag = next((f for f in risk.flags if f.code == "LOOKALIKE_DOMAIN"), None)
            known = flag.evidence[1] if flag and len(flag.evidence) > 1 else None
            lookalike = {"sender_domain": inv.get("from_domain"), "known_domain": known,
                         "diff": lookalike_diff(inv.get("from_domain") or "", known or "") if known else []}
        risk_view = {
            "points": risk.points, "tier": risk.tier, "action": risk.action, "sender_status": risk.sender_status,
            "amount_ratio": amount_ratio(risk), "lookalike": lookalike,
            "flags": [{"code": f.code, "points": f.points, "title": f.title, "detail": f.detail,
                       "evidence": list(f.evidence)} for f in risk.flags],
            "bank_changed": risk.bank_changed, "policy_version": risk.policy_version,
        }

    requested = None
    if risk and (risk.proposed_routing or risk.proposed_account):
        requested = {"bank_name": risk.proposed_bank_name, "routing": risk.proposed_routing,
                     "account_masked": _mask_acct(risk.proposed_account)}
    elif (ext.get("routing_number") or {}).get("value") or (ext.get("account_number") or {}).get("value"):
        requested = {"bank_name": (ext.get("bank_name") or {}).get("value"),
                     "routing": (ext.get("routing_number") or {}).get("value"),
                     "account_masked": _mask_acct((ext.get("account_number") or {}).get("value"))}
    destination = {
        "on_file": ({"bank_name": vendor["bank_name"], "routing": vendor["routing"],
                     "account_masked": _mask_acct(vendor["account"])} if vendor else None),
        "requested": requested,
        "changed": bool(risk and risk.bank_changed),
    }

    verification = None
    if ver:
        first_answer = None
        if ver.get("answer_channel"):
            first_answer = {"channel": ver.get("answer_channel"), "digits": ver.get("digits"),
                            "speech": ver.get("speech"), "confidence": ver.get("speech_confidence"),
                            "det_label": ver.get("det_label"), "llm_label": ver.get("llm_label")}
        verification = {"id": ver["id"], "source": ver["source"], "step": ver["step"],
                        "phone_masked": _mask_phone(ver.get("phone_called")), "events": ver.get("events") or [],
                        "first_answer": first_answer, "last4_ok": ver.get("last4_ok"),
                        "final_label": ver.get("final_label"), "attempts": ver.get("attempts") or 0}

    can_release_now = ledger.can_release(invoice_id, conn=conn)[0] if risk else False
    can_retry = ledger.retry_callback_allowed(invoice_id, conn=conn)
    actions = {
        "can_review": status == "NEEDS_REVIEW",
        "can_retry_call": can_retry,
        "can_simulate": bool(config.S.demo_mode and (status in ("CALL_PENDING", "CALLING") or can_retry)),
        "can_redteam": bool(risk) and not can_release_now,
    }
    analyst = inv.get("analyst") or {"status": "pending", "report": None}
    amount_cents = risk.amount_cents if risk else None

    return {
        "id": inv["id"], "status": status, "hold_reason": inv.get("hold_reason"), "source": inv["source"],
        "created_at": inv["created_at"],
        "invoice_number": fields["invoice_number"]["value"], "amount_cents": amount_cents,
        "decided_at": inv["updated_at"] if status in ("RELEASED", "HELD", "FAILED") else None,
        "email": {"from_name": inv.get("from_name"), "from_email": inv.get("from_email"),
                  "reply_to": inv.get("reply_to"), "subject": inv.get("subject"),
                  "received_at": inv.get("received_at"), "body_text": inv.get("body_text")},
        "extracted": {"fields": fields, "phone_numbers_in_email": ext.get("phone_numbers_in_email") or [],
                      "llm_status": ext.get("llm_status", "pending")},
        "vendor": vendor_view(conn, vendor) if vendor else None,
        "risk": risk_view,
        "destination": destination,
        "analyst": analyst,
        "verification": verification,
        "payment": payment_view(pay),
        "memo": inv.get("memo"),
        "trace": list_traces(conn, invoice_id),
        "audit": [{"seq": e["seq"], "ts": e["ts"], "actor": e["actor"], "event": e["event"],
                   "summary": e["summary"], "hash_short": e["hash_short"]}
                  for e in audit.list_entries(invoice_id, conn=conn)],
        "actions": actions,
        "ai_fallback": bool(inv.get("ai_fallback")),
    }
