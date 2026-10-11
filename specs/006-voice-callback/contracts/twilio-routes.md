# Contract: `/twilio/*` webhooks (PLAN.md §12.2, §12.3)

Caddy forwards `/twilio/*` to the app without basic auth (spec 002). Every route is `POST`, `application/x-www-form-urlencoded` from Twilio, `async def` (read the form), then one `run_in_threadpool` for all database and pipeline work. Responses are TwiML (`application/xml`) except the status route.

## Check order on every route (§12.2)

1. **Signature**: `RequestValidator(TWILIO_AUTH_TOKEN).validate(PUBLIC_BASE_URL + path + ("?" + query if query else ""), dict(form), X-Twilio-Signature)`. Fail, or no auth token configured → **403**, audit `webhook_rejected`; nothing else happens.
2. **Token**: sha256(token) → verification. Unknown, expired (> 15 min) or SUPERSEDED → `<Response><Say voice="Polly.Joanna-Neural">This verification line has expired.</Say><Hangup/></Response>` (status route: **204**).
3. **Final** (a retried webhook): no state change; replay DENIED → DENIED, CONFIRMED → L4_OK, anything else → UNCLEAR (status route: 204).
4. **CallSid**: must equal the stored `call_sid`; if none is stored, store it. Mismatch → treated like step 2.
5. **Idempotency**: state changes only through the pipeline (`transition()` and the verification `step`); a repeated webhook is a no-op.
6. Respond in **< 1 s**. No language model on the request path.

## Routes

| Route | Form fields used | Action | Response |
|---|---|---|---|
| `POST /twilio/voice/{token}` | `CallSid` | `on_call_status(id, "in-progress")` (the "Answered" event), `get_call_context(id)` | Q1 for the context inside the first Gather |
| `POST /twilio/answer/{token}` | `CallSid`, `Digits`, `SpeechResult`, `Confidence` | `decision = on_first_answer(id, Digits or None, SpeechResult or None, float(Confidence) or None)` | the script for `decision` (research R8) |
| `POST /twilio/last4/{token}` | `CallSid`, `Digits` | `on_last4(id, Digits or None)` | CONFIRMED → L4_OK, MISMATCH → L4_BAD, NO_INPUT → UNCLEAR; then `<Hangup/>` |
| `POST /twilio/status/{token}` | `CallSid`, `CallStatus` | `on_call_status(id, CallStatus)` | **204** (also for unknown or expired tokens) |

Empty strings from Twilio (`Digits=""`, `SpeechResult=""`) are passed as `None`.

## Gathers (§12.3, word for word)

- **First question**: `Gather(input="dtmf speech", num_digits=1, timeout=7, speech_timeout="auto", hints="yes, no, yes we did, no we didn't, that wasn't us, correct", action_on_empty_result=True, language="en-US", action=PUBLIC_BASE_URL + "/twilio/answer/{token}", method="POST")`
- **Last four**: `Gather(input="dtmf", num_digits=4, timeout=10, finish_on_key="#", action=PUBLIC_BASE_URL + "/twilio/last4/{token}", method="POST")`, followed by `<Redirect method="POST">` to the same action so silence still reaches `on_last4` (research R6).

## Placing the call (§12.1, verbatim)

`client.calls.create(to=phone_called, from_=TWILIO_FROM_NUMBER, url=PUBLIC_BASE_URL + "/twilio/voice/{token}", method="POST", status_callback=PUBLIC_BASE_URL + "/twilio/status/{token}", status_callback_event=["initiated", "ringing", "answered", "completed"], status_callback_method="POST", timeout=25)` → `call.sid`.
