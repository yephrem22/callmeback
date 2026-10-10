"""Merge regex and model extractions (PLAN.md §9.3). Text beats model: any
digits the model returns must appear verbatim in the body or they are dropped."""
from __future__ import annotations

import re

from app.intake.regex_extract import RegexExtraction, normalize_amount
from app.models import ExtractionResult, FieldValue, InvoiceExtraction
from core.checks import find_us_phones

_NOISE = re.compile(r"\b(accounts receivable|billing|invoices|team|ar)\b", re.I)
_DIGIT_JUNK = re.compile(r"[\s\-]")


def _digits_only(s: str | None) -> str:
    return _DIGIT_JUNK.sub("", s or "")


def _in_body(value: str | None, body_norm: str) -> bool:
    v = _digits_only(value)
    return bool(v) and v in body_norm


def vendor_name_from_header(from_name: str) -> str | None:
    cleaned = _NOISE.sub(" ", from_name or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,-|")
    return cleaned or None


def _field(regex_value: str | None, llm_value: str | None, body_norm: str,
           *, normalizer=lambda v: v) -> FieldValue:
    llm_norm = normalizer(llm_value) if llm_value else None
    if regex_value is not None:
        if llm_norm is not None and _digits_only(llm_norm) == _digits_only(regex_value):
            return FieldValue(value=regex_value, source="both", llm_value=llm_norm)
        if llm_norm is not None:
            return FieldValue(value=regex_value, source="regex", llm_value=llm_norm, mismatch=True)
        return FieldValue(value=regex_value, source="regex")
    if llm_norm is not None and _in_body(llm_norm, body_norm):
        return FieldValue(value=llm_norm, source="llm", llm_value=llm_norm)
    return FieldValue(value=None, source="none", llm_value=llm_norm)


def _text_field(regex_value: str | None, llm_value: str | None) -> FieldValue:
    if regex_value:
        if llm_value and llm_value.strip().lower() == regex_value.strip().lower():
            return FieldValue(value=regex_value, source="both", llm_value=llm_value)
        return FieldValue(value=regex_value, source="regex", llm_value=llm_value or None,
                          mismatch=bool(llm_value))
    if llm_value:
        return FieldValue(value=llm_value.strip(), source="llm", llm_value=llm_value)
    return FieldValue(value=None, source="none")


def merge(regex: RegexExtraction, llm: InvoiceExtraction | None, body: str, from_name: str,
          llm_status: str) -> ExtractionResult:
    body_norm = _digits_only(body)
    l = llm

    if l is not None and l.vendor_name:
        vendor = FieldValue(value=l.vendor_name.strip(), source="llm", llm_value=l.vendor_name)
    else:
        vendor = FieldValue(value=vendor_name_from_header(from_name), source="header")

    return ExtractionResult(
        vendor_name=vendor,
        invoice_number=_field(regex.invoice_number, l.invoice_number if l else None, body_norm),
        amount=_field(regex.amount, l.amount if l else None, body_norm, normalizer=normalize_amount),
        due_date=_text_field(regex.due_date, l.due_date if l else None),
        bank_name=_text_field(regex.bank_name, l.bank_name if l else None),
        routing_number=_field(regex.routing, l.routing_number if l else None, body_norm),
        account_number=_field(regex.account, l.account_number if l else None, body_norm),
        phone_numbers_in_email=find_us_phones(body),
        requests_payment_change=(l.requests_payment_change if l is not None else None),
        llm_status=llm_status,  # type: ignore[arg-type]
    )


def has_mismatch(result: ExtractionResult, regex: RegexExtraction) -> bool:
    """True when the merge saw a regex/LLM disagreement or two different numbers (§9.2, §10.2)."""
    return regex.mismatch or any(
        getattr(result, f).mismatch for f in ("invoice_number", "amount", "routing_number", "account_number"))
