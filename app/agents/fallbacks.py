"""Rules-only fallbacks (PLAN.md §11.4; spec FR-004..FR-006). The decision never depends on these.

Stored shapes (data-model.md):
    analyst = {"status": "pending"|"done"|"fallback"|"error", "report": AnalystReport|null}
    memo    = {"text": str, "by": "agent"|"fallback"}
"""
from __future__ import annotations

from app.models import AnalystReport, RiskResult, VerifierLabel

_HEADLINE = {
    "CALLBACK": "Held for a callback to the vendor's number on file",
    "REVIEW": "Needs a human review before payment",
    "HOLD_MANUAL": "Held: no vendor record to verify against",
    "AUTO_RELEASE": "Normal invoice, released automatically",
}
_NEXT = {
    "CALLBACK": "Wait for the callback to the number on file; do not use contact details from the email.",
    "REVIEW": "Review the amount against this vendor's history, then approve or reject.",
    "HOLD_MANUAL": "Onboard the vendor through procurement before any payment.",
    "AUTO_RELEASE": "No action needed.",
}


def analyst_fallback(risk: RiskResult | dict) -> AnalystReport:
    r = risk if isinstance(risk, RiskResult) else RiskResult.model_validate(risk)
    weighted = [f for f in r.flags if f.points > 0]
    if weighted:
        explanation = (f"{r.points} risk points ({r.tier}). "
                       + "; ".join(f"{f.title} (+{f.points})" for f in weighted) + ".")
    else:
        explanation = f"{r.points} risk points ({r.tier}). No risk flags; the details match the vendor record."
    return AnalystReport(
        headline=_HEADLINE.get(r.action, "Scored by policy"),
        explanation=explanation,
        cited_flags=[f.code for f in weighted],
        additional_concerns=[],
        recommended_next_step=_NEXT.get(r.action, "Follow the policy decision."),
    )


def analyst_record(report: AnalystReport | None, status: str) -> dict:
    return {"status": status, "report": report.model_dump() if report is not None else None}


def verifier_fallback() -> VerifierLabel:
    return VerifierLabel(label="UNCLEAR",
                         rationale="Verifier unavailable; a spoken yes needs the verifier, so this stays unclear.")


def payments_memo(vendor_name: str | None, amount_display: str, released: bool, reason: str) -> str:
    who = vendor_name or "the sender"
    if released:
        return (f"Released {amount_display} to {who} at the account on file. "
                f"Policy allowed it: {reason}.")
    return (f"Held {amount_display} for {who}. "
            f"Policy did not allow release: {reason}.")


def memo_record(text: str, by: str) -> dict:
    return {"text": text, "by": by}
