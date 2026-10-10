"""Masking (PLAN.md §6): outside the DB show only the last four digits of
account numbers (••••9942) and phone numbers (•••-•••-1234). Routing numbers
are public bank identifiers and stay in full (PLAN.md §7.6)."""
from __future__ import annotations

import re
from typing import Any

_DIGITS = re.compile(r"\d")
_LONG_NUMBER = re.compile(r"^\+?\d{10,}$")


def _last4(s: str) -> str:
    digits = "".join(_DIGITS.findall(s))
    return digits[-4:] if len(digits) >= 4 else digits


def mask_account(s: str | None) -> str | None:
    if s is None:
        return None
    return "••••" + _last4(str(s))


def mask_phone(s: str | None) -> str | None:
    if s is None:
        return None
    return "•••-•••-" + _last4(str(s))


def _is_routing_key(key: str) -> bool:
    return key.startswith("routing")


def _is_account_key(key: str) -> bool:
    return "account" in key and not key.endswith("_masked")


def _is_phone_key(key: str) -> bool:
    return ("phone" in key and not key.endswith("_masked")) or key.endswith("_phone")


def masked(data: Any, key: str = "") -> Any:
    """Recursively mask account and phone numbers in dicts/lists/strings."""
    if isinstance(data, dict):
        return {k: masked(v, str(k)) for k, v in data.items()}
    if isinstance(data, list):
        return [masked(v, key) for v in data]
    if isinstance(data, str):
        if key and _is_routing_key(key):
            return data
        if key and _is_account_key(key):
            return mask_account(data) if _DIGITS.search(data) else data
        if key and _is_phone_key(key):
            return mask_phone(data) if _DIGITS.search(data) else data
        if _LONG_NUMBER.match(data.strip()):
            return mask_account(data)
        return data
    return data
