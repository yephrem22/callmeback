"""Core Pydantic v2 contracts, copied verbatim from PLAN.md §7.4
(specs/003-core-engine/contracts/models.md). FROZEN after milestone A1."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Tier = Literal["GREEN", "YELLOW", "RED"]
Action = Literal["AUTO_RELEASE", "REVIEW", "CALLBACK", "HOLD_MANUAL"]


class Flag(BaseModel):
    code: str                 # e.g. "BANK_CHANGED" (full list in §10.2)
    points: int
    title: str                # user-facing, e.g. "Bank details differ from vendor record"
    detail: str               # specific: "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')"
    evidence: list[str] = []  # short quotes or values (masked)


class RiskResult(BaseModel):
    flags: list[Flag]
    points: int               # uncapped sum
    tier: Tier
    action: Action
    vendor_id: str | None
    sender_status: Literal["KNOWN", "LOOKALIKE", "UNRECOGNIZED", "NO_VENDOR"]
    bank_changed: bool
    proposed_bank_name: str | None
    proposed_routing: str | None   # raw in DB JSON; masked in API output
    proposed_account: str | None   # raw in DB JSON; masked in API output
    amount_cents: int | None
    median_cents: int | None
    policy_version: str = "2026-10-10.1"


class FieldValue(BaseModel):
    value: str | None
    source: Literal["regex", "llm", "both", "header", "none"]
    llm_value: str | None = None
    mismatch: bool = False    # regex and LLM disagreed; regex won


class ExtractionResult(BaseModel):
    vendor_name: FieldValue
    invoice_number: FieldValue
    amount: FieldValue        # normalized "48750.00"
    due_date: FieldValue
    bank_name: FieldValue
    routing_number: FieldValue
    account_number: FieldValue
    phone_numbers_in_email: list[str]
    requests_payment_change: bool | None   # LLM opinion, advisory only
    llm_status: Literal["pending", "ok", "fallback", "error"]   # "pending" while the fast path's Intake agent runs


class InvoiceExtraction(BaseModel):        # Intake agent structured output (see §11.4 for validators)
    vendor_name: str | None
    invoice_number: str | None
    amount: str | None                     # exactly as written, e.g. "$48,750.00"
    due_date: str | None
    bank_name: str | None
    routing_number: str | None             # digits exactly as in the email
    account_number: str | None
    phone_numbers: list[str] = []
    requests_payment_change: bool = False
    pressure_phrases: list[str] = []
    verification_avoidance_phrases: list[str] = []
    instructions_aimed_at_ai: bool = False


class AnalystReport(BaseModel):
    headline: str                          # ≤ 12 words
    explanation: str                       # ≤ 90 words, for a busy AP clerk
    cited_flags: list[str]                 # must be a subset of RiskResult flag codes
    additional_concerns: list[str] = []    # advisory; never changes points
    recommended_next_step: str


class VerifierLabel(BaseModel):
    label: Literal["CONFIRMED", "DENIED", "UNCLEAR"]
    rationale: str                         # ≤ 200 chars


class CallContext(BaseModel):
    verification_id: str
    subject_id: str
    kind: Literal["invoice", "change_case"]
    payer_name: str
    counterparty_name: str                 # vendor name or account name
    amount_cents: int | None
    change_type: Literal["bank_account", "billing_contact", "payment_details", "remit_address", "admin_contact", "other"]
    expected_last4: str | None             # only for bank_account
    phone_to_call: str                     # E.164; change cases always DEMO_VENDOR_PHONE
    attempts: int
