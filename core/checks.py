"""Pure checks shared by the app and the MCP service (PLAN.md §5, §9.2, §10.1):
ABA checksum, domain lookalike, US phone finder."""
from __future__ import annotations

import re

from rapidfuzz.distance import DamerauLevenshtein

# ---- ABA routing checksum (PLAN.md §10.2) -------------------------------------

def aba_valid(r: str | None) -> bool:
    """9 digits and (3*(d1+d4+d7) + 7*(d2+d5+d8) + (d3+d6+d9)) % 10 == 0."""
    if not r or not re.fullmatch(r"\d{9}", r):
        return False
    d = [int(ch) for ch in r]
    return (3 * (d[0] + d[3] + d[6]) + 7 * (d[1] + d[4] + d[7]) + (d[2] + d[5] + d[8])) % 10 == 0


# ---- Lookalike domains (PLAN.md §10.1, verbatim) ------------------------------

HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "i": "l", "|": "l", "3": "e", "5": "s", "$": "s"})


def skeleton(domain: str) -> str:
    d = domain.lower().strip().removeprefix("www.")
    d = d.replace("rn", "m").replace("vv", "w").translate(HOMOGLYPHS)
    return d.replace("-", "")


def is_lookalike(sender: str, known: str) -> bool:
    if "." not in sender or "." not in known:
        return False                       # not a domain
    if sender == known or sender.endswith("." + known):
        return False                       # exact or subdomain: KNOWN, not lookalike
    if skeleton(sender) == skeleton(known):
        return True                        # acme-supp1y.com vs acme-supply.com
    s_label, s_tld = sender.rsplit(".", 1)
    k_label, k_tld = known.rsplit(".", 1)
    if s_label == k_label and s_tld != k_tld:
        return True                        # acme-supply.co vs acme-supply.com
    return len(k_label) >= 6 and DamerauLevenshtein.distance(s_label, k_label) <= 2


def lookalike_diff(sender: str, known: str) -> list[dict]:
    """Character positions where the two domains differ after alignment, for
    the §7.6 `risk.lookalike.diff` field. Empty when lengths differ and the
    difference is not a single insertion/deletion."""
    s, k = sender.lower(), known.lower()
    if len(s) == len(k):
        return [{"index": i, "sender": a, "known": b} for i, (a, b) in enumerate(zip(s, k, strict=True)) if a != b]
    return []


def explain_lookalike(sender: str, known: str) -> str:
    """Human detail, e.g. "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')"."""
    s, k = sender.lower(), known.lower()
    head = f"{s} imitates {k}"
    if len(s) == len(k):
        diffs = lookalike_diff(s, k)
        if len(diffs) == 1:
            d = diffs[0]
            return f"{head} ('{d['sender']}' in place of '{d['known']}')"
        if 1 < len(diffs) <= 3:
            return head + " (" + ", ".join(f"'{d['sender']}' in place of '{d['known']}'" for d in diffs) + ")"
    s_label, s_tld = s.rsplit(".", 1)
    k_label, k_tld = k.rsplit(".", 1)
    if s_label == k_label and s_tld != k_tld:
        return f"{head} (.{s_tld} in place of .{k_tld})"
    if len(s) == len(k) + 1:
        for i in range(len(k) + 1):
            if s[:i] + s[i + 1:] == k:
                return f"{head} (added '{s[i]}')"
    if len(k) == len(s) + 1:
        for i in range(len(s) + 1):
            if k[:i] + k[i + 1:] == s:
                return f"{head} (missing '{k[i]}')"
    if skeleton(s) == skeleton(k):
        return f"{head} (same letters once look-alike characters and hyphens are normalised)"
    return f"{head} (differs by {DamerauLevenshtein.distance(s_label, k_label)} characters)"


# ---- US phone finder (PLAN.md §9.2) --------------------------------------------

# Requires separators or parentheses, so a 10-digit account number is never a phone.
_PHONE = re.compile(r"\(\d{3}\)\s?\d{3}[-.\s]\d{4}|\b\d{3}[-.]\d{3}[-.]\d{4}\b")


def find_us_phones(text: str) -> list[str]:
    return _PHONE.findall(text or "")
