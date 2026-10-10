"""Keyword lists and the phrase scanner (PLAN.md §10.3). Pure; shared with the
MCP service. Points come only from these lists, never from a model."""
from __future__ import annotations

import re

URGENCY = [
    "today", "immediately", "urgent", "urgently", "asap", "as soon as possible", "right away",
    "end of day", "by eod", "within the hour", "final notice", "overdue",
]

AVOID_VERIFICATION = [
    "do not call", "don't call", "dont call", "can't take calls", "cannot take calls",
    "unable to take calls", "not available by phone", "call my cell", "my cell", "new phone number",
    "phones are being upgraded", "email only", "only reply by email", "just reply to this email",
    "skip the callback", "no need to call", "no need to verify", "do not contact",
]

AI_DIRECTED = [
    "note for automated", "automated ap assistant", "ai assistant", "automated assistant",
    "language model", "ignore previous instructions", "ignore all previous", "system prompt", "as an ai",
]

_QUOTES = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                         "“": '"', "”": '"', "„": '"', "‟": '"'})
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, straight quotes, every whitespace run (including line breaks) → one space."""
    return _WS.sub(" ", (text or "").lower().translate(_QUOTES)).strip()


def _pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


_COMPILED: dict[str, re.Pattern[str]] = {}


def find_phrases(text: str, phrases: list[str]) -> list[str]:
    """Phrases from `phrases` that occur in `text` as standalone words, each at
    most once, in list order. `text` is normalised here."""
    norm = normalize(text)
    hits = []
    for p in phrases:
        pat = _COMPILED.get(p)
        if pat is None:
            pat = _COMPILED[p] = _pattern(p)
        if pat.search(norm):
            hits.append(p)
    return hits


def scan(subject: str, body: str) -> dict[str, list[str]]:
    """All three lists against subject and body together."""
    text = f"{subject or ''}\n{body or ''}"
    return {
        "URGENCY": find_phrases(text, URGENCY),
        "AVOID_VERIFICATION": find_phrases(text, AVOID_VERIFICATION),
        "AI_DIRECTED": find_phrases(text, AI_DIRECTED),
    }
