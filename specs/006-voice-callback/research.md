# Research: Voice Callback Verification (spec 006)

No NEEDS CLARIFICATION remained after reading PLAN.md §12, the merged spec 005 code (`app/pipeline.py`, `app/voice_port.py`, `app/verifications.py`) and the installed Twilio 9.11.2 library.

## R1. Where the §12.5 logic lives

- **Decision**: the routes call the existing `app/pipeline.py` functions (`get_call_context`, `on_first_answer`, `on_last4`, `on_call_status`); `app/voice/` holds no decision logic. `app/voice_port.py` already imports `app.voice.twilio_client.place_call/cancel_call` and `app.voice.classify.classify_answer` when they exist, so adding those modules switches the pipeline from stubs to the real thing with no pipeline edit.
- **Rationale**: PLAN.md §12.5 is owner A's and has merged with tests; duplicating it in the voice module would create two decision paths.
- **Alternatives**: re-implementing the handlers in `routes.py` (rejected: drift, and the simulate path would differ from the phone path, breaking §12.6 "same code path").

## R2. Route shape and the threadpool

- **Decision**: each route is `async def`, does `form = await request.form()`, runs the signature check (pure, CPU only), then does all database and pipeline work in one `await run_in_threadpool(fn)` call and renders TwiML from its result (PLAN.md §6, §12.2 step 1).
- **Rationale**: SQLite and the pipeline are synchronous; the event loop must never block on them. One threadpool hop per request keeps latency low.
- **Alternatives**: plain `def` routes like `app/api.py` (rejected: §12.2 says `async def`, and form parsing is async in Starlette).

## R3. Signature validation

- **Decision**: `RequestValidator(S.twilio_auth_token).validate(url, dict(form), request.headers.get("X-Twilio-Signature", ""))` with `url = S.public_base_url + request.url.path + ("?" + query if query else "")`. An empty auth token rejects every request. `TWILIO_VALIDATE_SIGNATURE=0` skips the check for local tunnelling only, logs a warning on every request, and is refused (treated as 1) when `VOICE_MODE=twilio` and `DEMO_MODE=0`. On failure: HTTP 403 and audit `webhook_rejected` (actor `twilio`, subject null, data `{route, reason, token_sha8}`), written in the threadpool.
- **Rationale**: behind Caddy the app sees `http://app:8000/...`, not the URL Twilio signed (§12.2). Fail closed (constitution III). The token itself is never logged.
- **Alternatives**: reconstructing the URL from `X-Forwarded-*` headers (rejected: spoofable and not what §12.2 says).

## R4. Token lookup and states

- **Decision**: `tokens.lookup(token)` hashes with sha256, selects by `token_hash` (UNIQUE in the frozen schema), and returns `(ver, state)` with state `"expired"` (unknown, `expires_at` past, or `final_label == "SUPERSEDED"`), `"final"` (any other final label), or `"active"`. Expired → `<Say>This verification line has expired.</Say><Hangup/>` (status route: 204). Final → replay without state change: DENIED → DENIED, CONFIRMED → L4_OK, anything else → UNCLEAR (§12.2 step 3).
- **Rationale**: the §12.2 order (unknown/expired/SUPERSEDED before final) maps directly to these three states. `app.verifications.new_token/create` (spec 003) already generate `secrets.token_urlsafe(24)` and store only the hash with a 15-minute expiry.

## R5. CallSid match and the "Answered" event

- **Decision**: `tokens.match_call(ver, call_sid)` stores the incoming CallSid when none is stored (the first-fetch race) and returns False on a mismatch, in which case the route does not act (expiry TwiML; status 204). The voice route logs "Answered" by calling `pipeline.on_call_status(id, "in-progress")`, the same handler Twilio's `answered` status callback reaches. `pipeline.on_call_status` is changed to add a timeline event only when it advances the step, so the voice fetch and the status callback together write one "Answered".
- **Rationale**: one code path for "answered"; no duplicate timeline rows in the dashboard stepper.

## R6. TwiML and scripts

- **Decision**: `twiml.py` is pure: the §12.3 scripts as constants or format functions, the two Gathers with exactly the §12.3 settings, `Polly.Joanna-Neural` as `VOICE` with `VOICE_FALLBACK = "Polly.Joanna"`. Responses are `application/xml`. The last-four Gather is followed by `<Redirect method="POST">…/twilio/last4/{token}</Redirect>`, so silence posts an empty Digits and reaches `on_last4` → NO_INPUT → UNCLEAR. The first Gather uses `action_on_empty_result=True`, so silence reaches `on_first_answer` → UNCLEAR → REPROMPT, then UNCLEAR.
- **Neural voice**: the B2 spike on the VM played `Polly.Joanna-Neural` clearly (docs/decisions.md, 23:39 UTC), so it stays the default; switching to the fallback is a one-constant change recorded in `docs/voice.md`.
- **Rationale**: a `<Gather>` without `actionOnEmptyResult` falls through to the next verb on timeout; without the redirect the call would end with no decision until the `completed` status callback.

## R7. Spoken amounts and change descriptions

- **Decision**: `spoken_amount(cents)` → `"48,750 dollars"`; non-zero cents → `"4,120 dollars and 50 cents"`; `None` → `"the requested amount"`. Change-case descriptions: `bank_account` "bank account", `billing_contact` "billing contact", `payment_details` "payment details", `remit_address` "remit-to address", `admin_contact` "admin contact", `other` "account details".
- **Rationale**: §12.3 "Speak amounts as 48,750 dollars"; all five samples are whole-dollar amounts.

## R8. Decision → script mapping

| Pipeline result | TwiML |
|---|---|
| `on_first_answer` ASK_LAST4 | ASK_LAST4 inside the last-four Gather + redirect |
| DENIED | DENIED (change case: "make this change") + Hangup |
| REPROMPT | REPROMPT inside the first Gather |
| UNCLEAR | UNCLEAR + Hangup |
| CONFIRMED_NO_LAST4 | CONFIRMED_NO_LAST4 + Hangup |
| `on_last4` CONFIRMED | L4_OK + Hangup |
| MISMATCH | L4_BAD + Hangup |
| NO_INPUT | UNCLEAR + Hangup |

## R9. Placing and cancelling calls

- **Decision**: `place_call` is PLAN.md §12.1 verbatim (25 s ring timeout, status events initiated/ringing/answered/completed). `cancel_call(sid)` does `client.calls(sid).update(status="completed")` and swallows every exception with a warning (§7.5 "never raises"). The Client is created per call from settings. `request_callback` (spec 005) already turns a `place_call` exception into HELD(CALL_FAILED) and dials only `phone_called`.
- **Rationale**: per-call clients avoid stale credentials after a `.env` change on the VM.

## R10. The Verifier's question

- **Decision**: `pipeline.question_text(ctx)` returns `twiml.q1_text(ctx)`, the exact Q1 the vendor heard, replacing spec 005's approximation, so the Verifier sees "the exact question and transcript" (spec 005 FR-005).
- **Rationale**: one source for the wording; `twiml.py` imports nothing from the pipeline, so there is no import cycle.

## R11. The B2 spike

- **Decision**: delete `app/voice/spike.py`, its include in `app/main.py`, `tests/test_voice_spike.py` and `scripts/twilio_spike.py`; change `scripts/probe_edge.sh` to POST an unsigned request to `/twilio/status/<random>` and expect 403 (Caddy lets `/twilio/*` through without basic auth; the app's signature check rejects it). The spike's timings stay in `docs/decisions.md`.
- **Rationale**: spec 002 FR-017 and the `app/main.py` comment say spec 006 removes the spike; an unauthenticated route that answers TwiML should not outlive its purpose.

## R12. Proving "< 1 s and no model" (FR-006, SC-005)

- **Decision**: `test_voice_flow.py` runs the answer webhook with AI live, real thread pools and a fake Verifier model that sleeps 5 s; the response must arrive in < 1 s and before the model returns, and the decision TwiML must not depend on it. Every other route test asserts < 1 s with inline executors.
