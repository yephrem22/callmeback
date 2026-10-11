# Contract: scripts and classifier (PLAN.md §12.3, §12.4, verbatim)

Voice `Polly.Joanna-Neural`; if Twilio rejects it, `Polly.Joanna`. Speak amounts as "48,750 dollars" (research R7 for cents and missing amounts).

## Scripts, word for word

- **Q1, invoice bank change:** "Hello. This is the accounts payable verification line for {payer}. We received an email, appearing to come from {counterparty}, asking us to send a payment of {amount} to a new bank account. Did {counterparty} request this bank change? Say yes or press 1. Say no or press 2."
- **Q1, invoice without a bank change** (RED or lookalike, bank on file unchanged): "Hello. This is the accounts payable verification line for {payer}. We received an invoice for {amount}, appearing to come from {counterparty}. Did {counterparty} send this invoice? Say yes or press 1. Say no or press 2."
- **Q1, change case (P2):** "Hello. This is the verification line for {payer}. We received a request, appearing to come from {counterparty}, to change the {change description} on their account. Did your organization make this request? Say yes or press 1. Say no or press 2."
- **REPROMPT:** "Sorry, I didn't catch that. If this request really came from {counterparty}, press 1. If not, press 2." Use the same Gather.
- **ASK_LAST4:** "Thank you. To confirm, please enter the last four digits of the new account number on your keypad."
- **DENIED:** "Thank you for letting us know. We will not send this payment, and our team will follow up using the contact details we have on file. Goodbye." (For change cases, say "make this change" instead of "send this payment".)
- **UNCLEAR:** "We couldn't confirm this request, so we'll put it on hold and follow up. Goodbye."
- **L4_OK:** "Thank you. We've recorded your confirmation. Goodbye." This is deliberately neutral, because the Verifier may still downgrade the answer.
- **L4_BAD:** "Those digits don't match the request we received. We will hold this payment and follow up. Goodbye."
- **CONFIRMED_NO_LAST4** (no last-4 challenge): "Thank you. We've recorded your answer. Goodbye."
- **Expired line** (§12.2): "This verification line has expired."

## Classifier (§12.4, pure)

Order of checks:
1. Digits `"1"` → YES. Digits `"2"` → NO. Any other digits → UNCLEAR.
2. Otherwise classify the speech. Normalize it as in §10.3 (lowercase, straight quotes, collapsed whitespace; `core.phrases.normalize`), then:
   - **NO patterns:** `\bno\b`, `\bnope\b`, `\bnot\b`, `\bnot (us|ours|me)\b`, `\bwasn'?t (us|me)\b`, `\bdid ?n[o']?t\b`, `\bdidn'?t\b`, `\bnever\b`, `\bfraud\b`, `\bscam\b`, `\bdon'?t\b`, `\bdo not\b`, `\bincorrect\b`, `\bwrong\b`
   - **YES patterns:** `\byes\b`, `\byeah\b`, `\byep\b`, `\bcorrect\b`, `\bthat'?s right\b`, `\bwe did\b`, `\bthat was us\b`, `\bconfirm(ed)?\b`, `\baffirmative\b`
   - NO only → NO. YES only → YES. Both or neither → UNCLEAR.

| Input | Expected |
|---|---|
| "No, we never changed banks" | NO |
| "nope that wasn't us" | NO |
| "Yes we did" | YES |
| "yeah that's right" | YES |
| "yeah that's right we didn't change anything" | UNCLEAR |
| "I don't know" | NO (fail closed) |
| "That's not correct" | UNCLEAR |
| "No." | NO |
| "" | UNCLEAR |
| digits "1" | YES |
| digits "9" | UNCLEAR |
