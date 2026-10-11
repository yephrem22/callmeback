# Voice callback (spec 006)

The phone half of the callback. Decisions live in `app/pipeline.py` (spec 005, PLAN.md §12.5); `app/voice/` places calls, authenticates webhooks and speaks the scripts. Contracts: `specs/006-voice-callback/contracts/`.

## Modules (`app/voice/`)

| Module | Does |
|---|---|
| `classify.py` | §12.4 classifier: digits first, then the NO/YES patterns over `core.phrases.normalize` |
| `twiml.py` | §12.3 scripts word for word, the two Gathers, spoken amounts, Q1 selection, replay and expiry TwiML |
| `tokens.py` | sha256 token lookup → `active` / `final` / `expired`; CallSid match (stored on first sight) |
| `security.py` | signature check, `webhook_rejected` audit, access-log token redaction |
| `routes.py` | `POST /twilio/{voice,answer,last4,status}/{token}` |
| `twilio_client.py` | §12.1 `place_call`, best-effort `cancel_call` |

The pipeline reaches `place_call`, `cancel_call` and `classify_answer` through `app/voice_port.py`.

## Every webhook, in order (§12.2)

1. Signature: `RequestValidator(TWILIO_AUTH_TOKEN)` over `PUBLIC_BASE_URL + path + query`. Fail, or no auth token → 403 and a `webhook_rejected` audit row. The audit row stores the token's hash prefix, never the token.
2. Token: unknown, more than 15 minutes old, or SUPERSEDED → "This verification line has expired." (the status route returns 204).
3. Final: replay without changing anything (DENIED → DENIED, CONFIRMED → L4_OK, else UNCLEAR).
4. CallSid must match the stored one. If none is stored yet, it is stored.
5. One `run_in_threadpool` hop into the pipeline. No model runs on the request path; the Verifier runs in the background. Each webhook answers in < 1 s.

Replays are safe:
- The answer Gather's action carries `?n=<attempt>`. An already-recorded `n` re-says the current prompt instead of counting as a second answer.
- Status callbacks audit only when they advance the step, and `completed` is handled once.

## Modes

- `VOICE_MODE=simulated` (the default) places no call. The demo buttons drive `simulate_answer`: the same code path, with actor `demo` and `"simulated": true`.
- `VOICE_MODE=twilio` dials `phone_called` (the vendor's `phone_on_file`, or `DEMO_VENDOR_PHONE` for change cases). A failure to place the call holds the invoice with CALL_FAILED, which is retryable.
- `TWILIO_VALIDATE_SIGNATURE=0` is honored only in simulated mode. In twilio mode it is ignored, with a warning.

## Troubleshooting (PLAN.md §16.5)

- **403 on every webhook live**: `PUBLIC_BASE_URL` doesn't exactly match the URL Twilio called (scheme, host, no trailing slash). Fix the configuration; never turn the check off.
- **Twilio error 11200**: the app was slow or unreachable. Check `docker compose logs app` and the Caddy `/twilio/*` route.
- **Edge check**: `scripts/probe_edge.sh HOST` expects an unsigned `POST /twilio/status/<random>` to get 403.
- **Voice**: `twiml.VOICE = "Polly.Joanna-Neural"`, which the B2 spike confirmed. If Twilio ever rejects it, set it to `twiml.VOICE_FALLBACK` (`Polly.Joanna`); the scripts stay the same.
- **Confirmed path on stage**: press 1. A spoken "yes" needs the Verifier's agreement, and with AI off it always holds.
