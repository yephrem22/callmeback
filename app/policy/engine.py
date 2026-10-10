"""Deterministic policy engine (PLAN.md §10). Reads only the invoice and the
DB, never a model. Same input → same RiskResult."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from rapidfuzz import fuzz

from app import repo
from app.intake.eml import ParsedEmail
from app.intake.regex_extract import amount_to_cents
from app.models import Action, ExtractionResult, Flag, RiskResult, Tier
from core import phrases
from core.checks import aba_valid, explain_lookalike, find_us_phones, is_lookalike

POLICY_VERSION = "2026-10-10.1"

_DROP_TOKENS = {"inc", "llc", "co", "corp", "company", "ltd", "the", "billing", "ar", "accounts",
                "receivable", "invoices", "team"}

TITLES = {
    "BANK_CHANGED": "Bank details differ from vendor record",
    "LOOKALIKE_DOMAIN": "Sender domain imitates the vendor's",
    "UNRECOGNIZED_SENDER": "Sender domain not on file for this vendor",
    "UNKNOWN_VENDOR": "No vendor record found",
    "INVALID_ROUTING": "Routing number fails ABA checksum",
    "REPLY_TO_MISMATCH": "Replies go to a different domain",
    "AMOUNT_3X": "Amount is {n}× this vendor's median",
    "AMOUNT_2X": "Amount is {n}× this vendor's median",
    "URGENCY": "Pressure to pay fast",
    "AVOID_VERIFICATION": "Discourages verification",
    "AI_DIRECTED_TEXT": "Contains instructions aimed at AI assistants",
    "PHONE_IN_EMAIL": "Email supplies its own phone number (ignored)",
    "NO_BANK_DETAILS": "No bank details; pay to the account on file",
    "EXTRACTION_MISMATCH": "AI and text disagreed; text used",
}

POINTS = {
    "BANK_CHANGED": 50, "LOOKALIKE_DOMAIN": 40, "UNRECOGNIZED_SENDER": 25, "UNKNOWN_VENDOR": 30,
    "INVALID_ROUTING": 30, "REPLY_TO_MISMATCH": 20, "AMOUNT_3X": 25, "AMOUNT_2X": 15, "URGENCY": 10,
    "AVOID_VERIFICATION": 15, "AI_DIRECTED_TEXT": 0, "PHONE_IN_EMAIL": 0, "NO_BANK_DETAILS": 0,
    "EXTRACTION_MISMATCH": 0,
}


def norm_name(s: str | None) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    tokens = [t for t in s.split() if t not in _DROP_TOKENS]
    return " ".join(tokens)


@dataclass
class Resolution:
    vendor: dict | None
    sender_status: str          # KNOWN | LOOKALIKE | UNRECOGNIZED | NO_VENDOR
    known_domain: str | None    # the vendor domain a lookalike imitates


def resolve_vendor(conn: sqlite3.Connection, from_domain: str, vendor_name: str | None) -> Resolution:
    vendors = repo.list_vendors(conn)
    from_domain = (from_domain or "").lower()
    # 1. exact domain or subdomain
    for v in vendors:
        for d in v["domains"]:
            if from_domain == d or from_domain.endswith("." + d):
                return Resolution(v, "KNOWN", None)
    # 2. lookalike domain
    for v in vendors:
        for d in v["domains"]:
            if is_lookalike(from_domain, d):
                return Resolution(v, "LOOKALIKE", d)
    # 3. fuzzy name
    name = norm_name(vendor_name)
    if name:
        for v in vendors:
            if fuzz.token_set_ratio(name, norm_name(v["name"])) >= 85:
                return Resolution(v, "UNRECOGNIZED", None)
    return Resolution(None, "NO_VENDOR", None)


def _flag(code: str, detail: str, evidence: list[str] | None = None, *, n: str | None = None) -> Flag:
    title = TITLES[code].format(n=n) if n is not None else TITLES[code]
    return Flag(code=code, points=POINTS[code], title=title, detail=detail, evidence=evidence or [])


def tier_for(points: int) -> Tier:
    if points < 20:
        return "GREEN"
    if points < 50:
        return "YELLOW"
    return "RED"


def route(codes: set[str], tier: Tier) -> Action:
    if "UNKNOWN_VENDOR" in codes:
        return "HOLD_MANUAL"
    if "BANK_CHANGED" in codes or "LOOKALIKE_DOMAIN" in codes or tier == "RED":
        return "CALLBACK"
    if tier == "YELLOW":
        return "REVIEW"
    return "AUTO_RELEASE"


def _mask_acct(a: str | None) -> str:
    return "••••" + a[-4:] if a else "none"


def score(conn: sqlite3.Connection, parsed: ParsedEmail, extraction: ExtractionResult,
          res: Resolution, *, extraction_mismatch: bool = False) -> RiskResult:
    vendor = res.vendor
    flags: list[Flag] = []
    routing = extraction.routing_number.value
    account = extraction.account_number.value
    amount_cents = amount_to_cents(extraction.amount.value)
    median = repo.vendor_median_cents(conn, vendor["id"]) if vendor else None
    history_n = repo.vendor_history_count(conn, vendor["id"]) if vendor else 0

    # BANK_CHANGED: a present routing or account differs from the master; missing never counts.
    bank_changed = False
    if vendor and res.sender_status != "NO_VENDOR":
        diffs = []
        if routing and routing != vendor["routing"]:
            diffs.append(f"routing {routing} vs {vendor['routing']} on file")
        if account and account != vendor["account"]:
            diffs.append(f"account {_mask_acct(account)} vs {_mask_acct(vendor['account'])} on file")
        if diffs:
            bank_changed = True
            new_bank = extraction.bank_name.value or "an unnamed bank"
            flags.append(_flag("BANK_CHANGED",
                               f"Email asks for payment to {new_bank}; vendor record has {vendor['bank_name']}",
                               diffs))

    if res.sender_status == "LOOKALIKE" and res.known_domain:
        flags.append(_flag("LOOKALIKE_DOMAIN", explain_lookalike(parsed.from_domain, res.known_domain),
                           [parsed.from_domain, res.known_domain]))
    elif res.sender_status == "UNRECOGNIZED" and vendor:
        flags.append(_flag("UNRECOGNIZED_SENDER",
                           f"{parsed.from_domain} is not one of {vendor['name']}'s domains ({', '.join(vendor['domains'])})",
                           [parsed.from_domain]))
    elif res.sender_status == "NO_VENDOR":
        who = extraction.vendor_name.value or parsed.from_domain
        flags.append(_flag("UNKNOWN_VENDOR", f"No vendor master record matches {who} or {parsed.from_domain}",
                           [parsed.from_domain]))

    if routing and not aba_valid(routing):
        flags.append(_flag("INVALID_ROUTING", f"{routing} fails the ABA checksum", [routing]))

    if parsed.reply_to_domain and parsed.reply_to_domain != parsed.from_domain:
        flags.append(_flag("REPLY_TO_MISMATCH", f"Replies go to {parsed.reply_to_domain}, not {parsed.from_domain}",
                           [parsed.reply_to]))

    ratio = None
    if vendor and history_n >= 3 and median and amount_cents is not None:
        ratio = amount_cents / median
        n = f"{ratio:.1f}"
        detail = f"${amount_cents / 100:,.2f} against a median of ${median / 100:,.2f} over the last {history_n} invoices"
        if ratio >= 3:
            flags.append(_flag("AMOUNT_3X", detail, [f"{ratio:.2f}×"], n=n))
        elif ratio >= 2:
            flags.append(_flag("AMOUNT_2X", detail, [f"{ratio:.2f}×"], n=n))

    hits = phrases.scan(parsed.subject, parsed.body_text)
    if hits["URGENCY"]:
        flags.append(_flag("URGENCY", "Language pressing for immediate payment: " + ", ".join(f'"{h}"' for h in hits["URGENCY"]),
                           hits["URGENCY"]))
    if hits["AVOID_VERIFICATION"]:
        flags.append(_flag("AVOID_VERIFICATION", "Language steering away from a callback: " + ", ".join(f'"{h}"' for h in hits["AVOID_VERIFICATION"]),
                           hits["AVOID_VERIFICATION"]))
    if hits["AI_DIRECTED"]:
        flags.append(_flag("AI_DIRECTED_TEXT", "Text addressed to automated assistants: " + ", ".join(f'"{h}"' for h in hits["AI_DIRECTED"]),
                           hits["AI_DIRECTED"]))

    phones = find_us_phones(parsed.body_text)
    if phones:
        flags.append(_flag("PHONE_IN_EMAIL", "The email offers " + ", ".join(phones) + "; we only call the number on file",
                           phones))

    if vendor and res.sender_status != "NO_VENDOR" and not routing and not account:
        flags.append(_flag("NO_BANK_DETAILS", f"Pay to {vendor['bank_name']} {_mask_acct(vendor['account'])} on file"))

    if extraction_mismatch:
        flags.append(_flag("EXTRACTION_MISMATCH", "Two different numbers, or AI and text disagreed; the text value was used"))

    points = sum(f.points for f in flags)
    tier = tier_for(points)
    action = route({f.code for f in flags}, tier)
    return RiskResult(
        flags=flags, points=points, tier=tier, action=action,
        vendor_id=vendor["id"] if vendor else None,
        sender_status=res.sender_status,  # type: ignore[arg-type]
        bank_changed=bank_changed,
        proposed_bank_name=extraction.bank_name.value if bank_changed else None,
        proposed_routing=routing if bank_changed else None,
        proposed_account=account if bank_changed else None,
        amount_cents=amount_cents, median_cents=median, policy_version=POLICY_VERSION,
    )


def amount_ratio(risk: RiskResult) -> float | None:
    if risk.amount_cents is None or not risk.median_cents:
        return None
    return round(risk.amount_cents / risk.median_cents, 2)
