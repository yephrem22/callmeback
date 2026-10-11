"""PLAN.md §12.3: scripts word for word, gather settings, spoken amounts (contracts/scripts.md)."""
from __future__ import annotations

import pytest

from app import config
from app.models import CallContext
from app.voice import twiml

BASE = "https://cmb.test"
TOKEN = "tok_abc"
PAYER = "Northgate Manufacturing"
ACME = "Acme Supply Co."


@pytest.fixture(autouse=True)
def _base_url(monkeypatch):
    monkeypatch.setenv("PUBLIC_BASE_URL", BASE)
    monkeypatch.setenv("PAYER_NAME", PAYER)
    config.reload()
    yield
    config.reload()


def ctx(**kw) -> CallContext:
    base = dict(verification_id="ver_1", subject_id="inv_1", kind="invoice", payer_name=PAYER, counterparty_name=ACME,
                amount_cents=4875000, change_type="bank_account", expected_last4="9942", phone_to_call="+18165550199",
                attempts=0)
    return CallContext(**{**base, **kw})


Q1_BANK = (f"Hello. This is the accounts payable verification line for {PAYER}. We received an email, appearing to "
           f"come from {ACME}, asking us to send a payment of 48,750 dollars to a new bank account. Did {ACME} request "
           "this bank change? Say yes or press 1. Say no or press 2.")
Q1_INVOICE = (f"Hello. This is the accounts payable verification line for {PAYER}. We received an invoice for "
              f"48,750 dollars, appearing to come from {ACME}. Did {ACME} send this invoice? Say yes or press 1. "
              "Say no or press 2.")
Q1_CASE = (f"Hello. This is the verification line for {PAYER}. We received a request, appearing to come from {ACME}, "
           "to change the billing contact on their account. Did your organization make this request? Say yes or "
           "press 1. Say no or press 2.")
REPROMPT = f"Sorry, I didn't catch that. If this request really came from {ACME}, press 1. If not, press 2."
ASK_LAST4 = "Thank you. To confirm, please enter the last four digits of the new account number on your keypad."
DENIED = ("Thank you for letting us know. We will not send this payment, and our team will follow up using the "
          "contact details we have on file. Goodbye.")
DENIED_CASE = ("Thank you for letting us know. We will not make this change, and our team will follow up using the "
               "contact details we have on file. Goodbye.")
UNCLEAR = "We couldn't confirm this request, so we'll put it on hold and follow up. Goodbye."
L4_OK = "Thank you. We've recorded your confirmation. Goodbye."
L4_BAD = "Those digits don't match the request we received. We will hold this payment and follow up. Goodbye."
CONFIRMED_NO_LAST4 = "Thank you. We've recorded your answer. Goodbye."


def _has(xml: str, text: str) -> bool:
    return text in xml or text.replace("'", "&apos;") in xml


def test_scripts_word_for_word():
    assert twiml.q1_text(ctx()) == Q1_BANK
    assert twiml.q1_text(ctx(change_type="other", expected_last4=None)) == Q1_INVOICE
    assert twiml.q1_text(ctx(kind="change_case", change_type="billing_contact", amount_cents=None,
                             expected_last4=None)) == Q1_CASE
    assert twiml.reprompt_text(ctx()) == REPROMPT
    assert twiml.ASK_LAST4 == ASK_LAST4
    assert twiml.denied_text(ctx()) == DENIED
    assert twiml.denied_text(ctx(kind="change_case", change_type="billing_contact")) == DENIED_CASE
    assert (twiml.UNCLEAR, twiml.L4_OK, twiml.L4_BAD, twiml.CONFIRMED_NO_LAST4) == (UNCLEAR, L4_OK, L4_BAD,
                                                                                   CONFIRMED_NO_LAST4)


def test_spoken_amounts():
    assert twiml.spoken_amount(4875000) == "48,750 dollars"
    assert twiml.spoken_amount(412000) == "4,120 dollars"
    assert twiml.spoken_amount(412050) == "4,120 dollars and 50 cents"
    assert twiml.spoken_amount(None) == "the requested amount"


@pytest.mark.parametrize(("change", "words"), [("bank_account", "bank account"), ("billing_contact", "billing contact"),
                                               ("payment_details", "payment details"), ("remit_address", "remit-to address"),
                                               ("admin_contact", "admin contact"), ("other", "account details")])
def test_change_descriptions(change, words):
    assert f"to change the {words} on their account" in twiml.q1_text(
        ctx(kind="change_case", change_type=change, amount_cents=None, expected_last4=None))


def test_first_gather_settings():
    xml = twiml.voice_prompt(ctx(), TOKEN)
    for attr in ('input="dtmf speech"', 'numDigits="1"', 'timeout="7"', 'speechTimeout="auto"',
                 'hints="yes, no, yes we did, no we didn\'t, that wasn\'t us, correct"', 'actionOnEmptyResult="true"',
                 'language="en-US"', f'action="{BASE}/twilio/answer/{TOKEN}?n=1"', 'method="POST"'):
        assert attr in xml.replace("&apos;", "'"), attr
    assert _has(xml, Q1_BANK) and '<Say voice="Polly.Joanna-Neural">' in xml


def test_reprompt_uses_the_same_gather_for_attempt_two():
    xml = twiml.for_first_answer("REPROMPT", ctx(), TOKEN)
    assert f'action="{BASE}/twilio/answer/{TOKEN}?n=2"' in xml and 'numDigits="1"' in xml and _has(xml, REPROMPT)


def test_last4_gather_and_redirect():
    xml = twiml.for_first_answer("ASK_LAST4", ctx(), TOKEN)
    for attr in ('input="dtmf"', 'numDigits="4"', 'timeout="10"', 'finishOnKey="#"',
                 f'action="{BASE}/twilio/last4/{TOKEN}"'):
        assert attr in xml, attr
    assert _has(xml, ASK_LAST4)
    assert xml.index("</Gather>") < xml.index(f'<Redirect method="POST">{BASE}/twilio/last4/{TOKEN}</Redirect>')


@pytest.mark.parametrize(("decision", "text"), [("DENIED", DENIED), ("UNCLEAR", UNCLEAR),
                                                ("CONFIRMED_NO_LAST4", CONFIRMED_NO_LAST4)])
def test_first_answer_terminal_scripts(decision, text):
    xml = twiml.for_first_answer(decision, ctx(), TOKEN)
    assert _has(xml, text) and xml.endswith("<Hangup /></Response>") and "<Gather" not in xml


def test_change_case_denied_wording():
    xml = twiml.for_first_answer("DENIED", ctx(kind="change_case", change_type="billing_contact"), TOKEN)
    assert _has(xml, DENIED_CASE)


@pytest.mark.parametrize(("decision", "text"), [("CONFIRMED", L4_OK), ("MISMATCH", L4_BAD), ("NO_INPUT", UNCLEAR)])
def test_last4_scripts(decision, text):
    xml = twiml.for_last4(decision)
    assert _has(xml, text) and xml.endswith("<Hangup /></Response>")


@pytest.mark.parametrize(("label", "text"), [("DENIED", DENIED), ("CONFIRMED", L4_OK), ("UNCLEAR", UNCLEAR),
                                             ("NO_ANSWER", UNCLEAR), ("LAST4_MISMATCH", UNCLEAR),
                                             ("VERIFIER_DISAGREED", UNCLEAR)])
def test_final_replay(label, text):
    xml = twiml.for_final(label, ctx())
    assert _has(xml, text) and xml.endswith("<Hangup /></Response>")


def test_expired_line():
    xml = twiml.expired()
    assert '<Say voice="Polly.Joanna-Neural">This verification line has expired.</Say><Hangup /></Response>' in xml


def test_every_say_uses_the_neural_voice():
    xmls = [twiml.voice_prompt(ctx(), TOKEN), twiml.expired(), twiml.for_last4("CONFIRMED")] + [
        twiml.for_first_answer(d, ctx(), TOKEN) for d in ("ASK_LAST4", "DENIED", "REPROMPT", "UNCLEAR", "CONFIRMED_NO_LAST4")]
    for xml in xmls:
        assert xml.count("<Say") == xml.count('<Say voice="Polly.Joanna-Neural">') >= 1
    assert twiml.VOICE == "Polly.Joanna-Neural" and twiml.VOICE_FALLBACK == "Polly.Joanna"
