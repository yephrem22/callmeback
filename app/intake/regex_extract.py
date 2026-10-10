"""Label-anchored regex extraction (PLAN.md §9.2). Patterns are verbatim."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

PATTERNS = {
    "routing":        r"\b(?:routing|aba|rtn)(?:\s*(?:number|no\.|no\b|#))?\s*[:#]?\s*(\d{9})\b",
    "account":        r"\b(?:account|acct)(?:\s*(?:number|no\.|no\b|#))?\s*[:#]?\s*(\d{4,17})\b",
    "amount":         r"\b(?:amount due|total due|balance due|amount)\s*[:#]?\s*\$\s?([\d,]+(?:\.\d{2})?)",
    "invoice_number": r"\binvoice\s*(?:number|no\.|no\b|#)\s*[:#]?\s*([A-Z0-9][A-Z0-9-]{2,})",
    "bank_name":      r"^\s*bank\s*:\s*(.+?)\s*$",
    "due_date":       r"^\s*due date\s*:\s*(.+?)\s*$",
}
AMOUNT_FALLBACK = r"\$[\d,]+(?:\.\d{2})?"   # first dollar figure in the body, if "amount" found nothing

_FLAGS = re.IGNORECASE | re.MULTILINE
COMPILED = {k: re.compile(v, _FLAGS) for k, v in PATTERNS.items()}
_AMOUNT_FALLBACK = re.compile(AMOUNT_FALLBACK)


@dataclass
class RegexExtraction:
    routing: str | None = None
    account: str | None = None
    amount: str | None = None            # normalized "48750.00"
    invoice_number: str | None = None
    bank_name: str | None = None
    due_date: str | None = None
    mismatch: bool = False               # two different routing or account numbers seen
    all_routing: list[str] = field(default_factory=list)
    all_account: list[str] = field(default_factory=list)


def normalize_amount(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = raw.replace("$", "").replace(",", "").strip()
    try:
        return f"{Decimal(s):.2f}"
    except InvalidOperation:
        return None


def amount_to_cents(normalized: str | None) -> int | None:
    if normalized is None:
        return None
    try:
        return int((Decimal(normalized) * 100).to_integral_value())
    except InvalidOperation:
        return None


def _all(key: str, body: str) -> list[str]:
    return [m.group(1) for m in COMPILED[key].finditer(body)]


def extract(body: str) -> RegexExtraction:
    body = body or ""
    out = RegexExtraction()
    out.all_routing = _all("routing", body)
    out.all_account = _all("account", body)
    out.routing = out.all_routing[0] if out.all_routing else None
    out.account = out.all_account[0] if out.all_account else None
    out.mismatch = len(set(out.all_routing)) > 1 or len(set(out.all_account)) > 1

    amounts = _all("amount", body)
    if amounts:
        out.amount = normalize_amount(amounts[0])
    else:
        m = _AMOUNT_FALLBACK.search(body)
        out.amount = normalize_amount(m.group(0)) if m else None

    inv = _all("invoice_number", body)
    out.invoice_number = inv[0] if inv else None
    banks = _all("bank_name", body)
    out.bank_name = banks[0] if banks else None
    dues = _all("due_date", body)
    out.due_date = dues[0] if dues else None
    return out
