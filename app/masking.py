"""Masking (PLAN.md §6): outside the DB show only the last four digits of
account numbers (••••9942) and phone numbers (•••-•••-1234). Routing numbers
are public bank identifiers and stay in full (PLAN.md §7.6)."""
from __future__ import annotations

import re
from typing import Any

_DIGITS = re.compile(r"\d")
# A run of 10 to 17 digits (account numbers and E.164 phones); 9-digit routing numbers are untouched.
_LONG_RUN = re.compile(r"(?<!\d)\+?\d{10,17}(?!\d)")

# Keys whose values are identifiers, never secrets, even if they contain "account" or digits.
_SKIP_SUFFIXES = ("_masked", "_key", "_hash", "_sid", "_id", "_ref", "_url")


def _last4(s: str) -> str:
    digits = "".join(_DIGITS.findall(s))
    return digits[-4:] if len(digits) >= 4 else digits


def mask_account(s: str | int | None) -> str | None:
    if s is None:
        return None
    return "••••" + _last4(str(s))


def mask_phone(s: str | int | None) -> str | None:
    if s is None:
        return None
    return "•••-•••-" + _last4(str(s))


def _skip(key: str) -> bool:
    return key.endswith(_SKIP_SUFFIXES) or key in {"id", "seq", "sid", "key", "hash"}


def _is_routing_key(key: str) -> bool:
    return key.startswith("routing")


def _is_account_key(key: str) -> bool:
    return "account" in key and not _skip(key) and "sid" not in key


def _is_phone_key(key: str) -> bool:
    return "phone" in key and not _skip(key)


def _mask_runs(text: str) -> str:
    return _LONG_RUN.sub(lambda m: "••••" + m.group(0)[-4:], text)


def masked(data: Any, key: str = "") -> Any:
    """Recursively mask account and phone numbers in dicts, lists, strings and ints.

    - values under account-like keys → ••••1234; phone-like keys → •••-•••-1234
    - routing keys, and identifier keys (*_key, *_hash, *_sid, *_id, *_ref) → untouched
    - any other string: runs of 10–17 digits inside it are masked, so quoted
      evidence such as "wire to acct 4421984821" never leaks a full account number
    """
    if isinstance(data, dict):
        return {k: masked(v, str(k)) for k, v in data.items()}
    if isinstance(data, list):
        return [masked(v, key) for v in data]
    if isinstance(data, bool):
        return data
    if isinstance(data, int):
        if key and _is_account_key(key):
            return mask_account(data)
        if key and _is_phone_key(key):
            return mask_phone(data)
        return data
    if isinstance(data, str):
        if key and (_is_routing_key(key) or _skip(key)):
            return data
        if key and _is_account_key(key):
            return mask_account(data) if _DIGITS.search(data) else data
        if key and _is_phone_key(key):
            return mask_phone(data) if _DIGITS.search(data) else data
        return _mask_runs(data)
    return data
