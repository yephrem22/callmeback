"""Deterministic answer classifier (PLAN.md §12.4). Pure: no I/O, no model.

Digits decide first (1 → YES, 2 → NO, anything else → UNCLEAR). Otherwise the speech is
normalized as in §10.3 and matched against the NO and YES patterns: NO only → NO, YES only →
YES, both or neither → UNCLEAR. "I don't know" is NO on purpose: fail closed.
"""
from __future__ import annotations

import re
from typing import Literal

from core.phrases import normalize

Label = Literal["YES", "NO", "UNCLEAR"]

NO_PATTERNS = [re.compile(p) for p in (
    r"\bno\b", r"\bnope\b", r"\bnot\b", r"\bnot (us|ours|me)\b", r"\bwasn'?t (us|me)\b", r"\bdid ?n[o']?t\b",
    r"\bdidn'?t\b", r"\bnever\b", r"\bfraud\b", r"\bscam\b", r"\bdon'?t\b", r"\bdo not\b", r"\bincorrect\b",
    r"\bwrong\b",
)]
YES_PATTERNS = [re.compile(p) for p in (
    r"\byes\b", r"\byeah\b", r"\byep\b", r"\bcorrect\b", r"\bthat'?s right\b", r"\bwe did\b", r"\bthat was us\b",
    r"\bconfirm(ed)?\b", r"\baffirmative\b",
)]


def classify_answer(digits: str | None, speech: str | None) -> Label:
    if digits:
        return {"1": "YES", "2": "NO"}.get(digits, "UNCLEAR")  # type: ignore[return-value]
    text = normalize(speech or "")
    no = any(p.search(text) for p in NO_PATTERNS)
    yes = any(p.search(text) for p in YES_PATTERNS)
    if no and not yes:
        return "NO"
    if yes and not no:
        return "YES"
    return "UNCLEAR"
