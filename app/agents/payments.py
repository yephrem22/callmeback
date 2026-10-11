"""Payments agent (PLAN.md §11.4; spec FR-006).

Three tools, bound to one invoice by closure (no invoice-id parameter the model could change):
get_case_summary, release_payment (guarded by PaymentGuardPlugin, then re-checked by the ledger),
hold_payment. The AI can always say no: a hold on an eligible invoice becomes HELD(AGENT_HOLD).
If the agent fails, times out, or ends without calling release or hold, policy decides.
"""
from __future__ import annotations

from typing import Any

from strands import Agent, tool

from app import audit, config, db, ledger, repo
from app.agents import model as model_factory
from app.agents.fallbacks import memo_record, payments_memo
from app.agents.plugins import PaymentGuardPlugin, RateLimitPlugin, TracePlugin, agent_kwargs
from app.agents.runner import RunContext, run_agent
from app.ledger import PolicyViolation
from app.state import IllegalTransition

SYSTEM = ("You are the Payments agent for Northgate's AP team. Call get_case_summary first. If release_eligible is true, "
          "call release_payment. If it is false, call hold_payment with a one-line reason. Then write a two-sentence memo "
          "for the AP log. Never try to work around a blocked action.")

ACTIONS = {"release_payment", "hold_payment"}


def _amount_display(cents: int | None) -> str:
    return f"${cents / 100:,.2f}" if cents is not None else "the invoice amount"


def case_summary(invoice_id: str) -> dict[str, Any]:
    c = db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        risk = inv.get("risk") or {}
        ver = repo.latest_verification(c, invoice_id)
        vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
        ok, reason = ledger.can_release(invoice_id, conn=c)
        return {
            "status": inv["status"], "hold_reason": inv.get("hold_reason"), "tier": risk.get("tier"),
            "flags": [f["code"] for f in risk.get("flags", []) if f.get("points", 0) > 0],
            "verification_final_label": (ver or {}).get("final_label"),
            "amount": _amount_display(risk.get("amount_cents")),
            "destination_masked": repo.vendor_view(c, vendor)["bank_masked"] if vendor else None,
            "release_eligible": ok, "eligibility_reason": reason,
        }
    finally:
        c.close()


def make_payment_tools(invoice_id: str, ctx: RunContext, record: dict) -> list:
    called: list[str] = record.setdefault("called", [])

    @tool
    def get_case_summary() -> dict:
        """The case summary: status, tier, flags, verification result, amount, masked destination and whether release is eligible."""
        ctx.check()
        called.append("get_case_summary")
        return case_summary(invoice_id)

    @tool
    def release_payment() -> str:
        """Release this invoice's payment to the vendor account on file. Only allowed when release_eligible is true."""
        ctx.check()
        called.append("release_payment")
        try:
            pay_id = ledger.release(invoice_id, by="agent:payments")
            record["released"] = True
            return f"released: payment {pay_id} to the account on file"
        except PolicyViolation as e:
            return f"blocked: {e}"

    @tool
    def hold_payment(reason: str) -> str:
        """Hold this invoice's payment, with a one-line reason."""
        ctx.check()
        called.append("hold_payment")
        try:
            ledger.hold(invoice_id, reason, by="agent:payments")
            record["held"] = True
            return "held"
        except IllegalTransition as e:
            return f"cannot hold: {e}"

    return [get_case_summary, release_payment, hold_payment]


def build_payments_agent(invoice_id: str, ctx: RunContext, system_prompt: str = SYSTEM, agent_name: str = "payments",
                         model: Any = None) -> tuple[Agent, dict]:
    record: dict = {"called": []}
    agent = Agent(
        model=model if model is not None else model_factory.make_model(500),
        system_prompt=system_prompt,
        tools=make_payment_tools(invoice_id, ctx, record),
        plugins=[PaymentGuardPlugin(invoice_id, run_id=ctx.run_id, agent=agent_name),
                 TracePlugin(invoice_id, agent_name, ctx.run_id), RateLimitPlugin()],
        name=agent_name,
        **agent_kwargs(),
    )
    return agent, record


def run_payments(ctx: RunContext, invoice_id: str) -> dict:
    agent, record = build_payments_agent(invoice_id, ctx)
    result = agent(f"Process invoice {invoice_id}. Start with get_case_summary.", cancel_signal=ctx.cancel)
    memo = " ".join(str(result).split())
    return {"called": list(record["called"]), "memo": memo[:400]}


def payments_fallback(invoice_id: str) -> dict:
    """Policy decides: release by policy:auto if eligible, otherwise hold; template memo."""
    c = db.connect()
    try:
        inv = repo.get_invoice(c, invoice_id)
        vendor = repo.get_vendor(c, inv["vendor_id"]) if inv.get("vendor_id") else None
        amount = _amount_display((inv.get("risk") or {}).get("amount_cents"))
    finally:
        c.close()
    ok, reason = ledger.can_release(invoice_id)
    released = False
    if ok:
        try:
            ledger.release(invoice_id, by="policy:auto")
            released = True
        except PolicyViolation as e:
            reason = str(e)
    else:
        try:
            ledger.hold(invoice_id, reason, by="policy")
        except IllegalTransition:
            pass  # not in a holdable state (e.g. already decided); nothing to do
    text = payments_memo(vendor["name"] if vendor else inv.get("from_name"), amount, released, reason)
    audit.append(invoice_id, "policy", "memo_written",
                 {"by": "fallback", "note": "agent took no action; policy decided", "released": released})
    return {"called": [], "memo": text, "by": "fallback", "released": released}


def process_payments(invoice_id: str) -> dict:
    """Run the Payments agent once; policy decides if it fails or takes no action. Stores the memo."""
    out, outcome = run_agent("payments", invoice_id, lambda ctx: run_payments(ctx, invoice_id),
                             config.S.timeout_payments_s, lambda: payments_fallback(invoice_id))
    if outcome == "result":
        if not ACTIONS & set(out["called"]):
            out = payments_fallback(invoice_id)
        else:
            out = {**out, "by": "agent"}
            audit.append(invoice_id, "agent:payments", "memo_written", {"by": "agent", "memo": out["memo"]})
    c = db.connect()
    try:
        repo.update_invoice(c, invoice_id, memo=memo_record(out["memo"] or "No memo.", out["by"]))
    finally:
        c.close()
    return out
