"""TwiML and scripts for the verification line (PLAN.md §12.3; contracts/scripts.md). Pure.

Scripts are word for word. The first Gather's action carries the attempt it collects
(`?n=1`, `?n=2` after a reprompt) so a replayed webhook is never counted as a second answer
(analyze U1). The last-four Gather is followed by a Redirect to the same action, so silence
still reaches `on_last4` (research R6). Imports nothing from the pipeline.
"""
from __future__ import annotations

from twilio.twiml.voice_response import Gather, VoiceResponse

from app import config
from app.models import CallContext

VOICE = "Polly.Joanna-Neural"
VOICE_FALLBACK = "Polly.Joanna"          # if Twilio ever rejects the neural voice (PLAN.md §12.3)

HINTS = "yes, no, yes we did, no we didn't, that wasn't us, correct"
EXPIRED = "This verification line has expired."
ASK_LAST4 = "Thank you. To confirm, please enter the last four digits of the new account number on your keypad."
UNCLEAR = "We couldn't confirm this request, so we'll put it on hold and follow up. Goodbye."
L4_OK = "Thank you. We've recorded your confirmation. Goodbye."
L4_BAD = "Those digits don't match the request we received. We will hold this payment and follow up. Goodbye."
CONFIRMED_NO_LAST4 = "Thank you. We've recorded your answer. Goodbye."
_DENIED = ("Thank you for letting us know. We will not {action}, and our team will follow up using the contact "
           "details we have on file. Goodbye.")

CHANGE_DESCRIPTIONS = {
    "bank_account": "bank account", "billing_contact": "billing contact", "payment_details": "payment details",
    "remit_address": "remit-to address", "admin_contact": "admin contact", "other": "account details",
}


def spoken_amount(cents: int | None) -> str:
    """'48,750 dollars'; '4,120 dollars and 50 cents'; 'the requested amount' when unknown (research R7)."""
    if cents is None:
        return "the requested amount"
    dollars, rest = divmod(int(cents), 100)
    return f"{dollars:,} dollars" + (f" and {rest} cents" if rest else "")


def q1_text(ctx: CallContext) -> str:
    payer, who = ctx.payer_name, ctx.counterparty_name
    if ctx.kind == "change_case":
        return (f"Hello. This is the verification line for {payer}. We received a request, appearing to come from "
                f"{who}, to change the {CHANGE_DESCRIPTIONS.get(ctx.change_type, 'account details')} on their account. "
                "Did your organization make this request? Say yes or press 1. Say no or press 2.")
    amount = spoken_amount(ctx.amount_cents)
    if ctx.change_type == "bank_account":
        return (f"Hello. This is the accounts payable verification line for {payer}. We received an email, appearing "
                f"to come from {who}, asking us to send a payment of {amount} to a new bank account. Did {who} request "
                "this bank change? Say yes or press 1. Say no or press 2.")
    return (f"Hello. This is the accounts payable verification line for {payer}. We received an invoice for {amount}, "
            f"appearing to come from {who}. Did {who} send this invoice? Say yes or press 1. Say no or press 2.")


def reprompt_text(ctx: CallContext) -> str:
    return (f"Sorry, I didn't catch that. If this request really came from {ctx.counterparty_name}, press 1. "
            "If not, press 2.")


def denied_text(ctx: CallContext) -> str:
    return _DENIED.format(action="make this change" if ctx.kind == "change_case" else "send this payment")


# ---- TwiML ------------------------------------------------------------------------

def _url(path: str) -> str:
    return f"{config.S.public_base_url}{path}"


def _say_hangup(text: str) -> str:
    vr = VoiceResponse()
    vr.say(text, voice=VOICE)
    vr.hangup()
    return str(vr)


def first_gather(token: str, text: str, attempt: int) -> str:
    vr = VoiceResponse()
    g = Gather(input="dtmf speech", num_digits=1, timeout=7, speech_timeout="auto", hints=HINTS,
               action_on_empty_result=True, language="en-US", action=_url(f"/twilio/answer/{token}?n={attempt}"),
               method="POST")
    g.say(text, voice=VOICE)
    vr.append(g)
    return str(vr)


def last4_gather(token: str, text: str) -> str:
    vr = VoiceResponse()
    action = _url(f"/twilio/last4/{token}")
    g = Gather(input="dtmf", num_digits=4, timeout=10, finish_on_key="#", action=action, method="POST")
    g.say(text, voice=VOICE)
    vr.append(g)
    vr.redirect(action, method="POST")          # silence → empty Digits → NO_INPUT (research R6)
    return str(vr)


def voice_prompt(ctx: CallContext, token: str) -> str:
    """The answered call: Q1 inside the first Gather (attempt 1)."""
    return first_gather(token, q1_text(ctx), 1)


def for_first_answer(decision: str, ctx: CallContext, token: str) -> str:
    if decision == "ASK_LAST4":
        return last4_gather(token, ASK_LAST4)
    if decision == "REPROMPT":
        return first_gather(token, reprompt_text(ctx), 2)
    if decision == "DENIED":
        return _say_hangup(denied_text(ctx))
    if decision == "CONFIRMED_NO_LAST4":
        return _say_hangup(CONFIRMED_NO_LAST4)
    return _say_hangup(UNCLEAR)


def for_last4(decision: str) -> str:
    return _say_hangup({"CONFIRMED": L4_OK, "MISMATCH": L4_BAD}.get(decision, UNCLEAR))


def for_final(final_label: str, ctx: CallContext) -> str:
    """Replay for a retried webhook on a finished verification (PLAN.md §12.2 step 3)."""
    if final_label == "DENIED":
        return _say_hangup(denied_text(ctx))
    if final_label == "CONFIRMED":
        return _say_hangup(L4_OK)
    return _say_hangup(UNCLEAR)


def expired() -> str:
    return _say_hangup(EXPIRED)
