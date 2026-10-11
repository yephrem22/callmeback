# Data Model: Voice Callback Verification (spec 006)

No schema change. Everything below lives in the frozen `verifications` table (PLAN.md §7.2, `app/schema.sql`) and the frozen `CallContext` model (PLAN.md §7.5, `app/models.py`).

## Verification (PLAN.md §7.2)

| Field | Written by | Notes |
|---|---|---|
| `id`, `subject_id`, `kind` | `pipeline.request_callback` / `simulate_answer` | `kind` is `invoice` or `change_case` |
| `token_hash` | `verifications.create` | sha256 hex of `secrets.token_urlsafe(24)`; the token itself only exists in the Twilio URLs |
| `expires_at` | `verifications.create` | created + 15 min |
| `call_sid` | `request_callback` after `place_call`; else the first webhook (`tokens.match_call`) | a webhook with a different CallSid is not acted on |
| `phone_called` | `request_callback` | vendor `phone_on_file`, or `DEMO_VENDOR_PHONE` for change cases; the only number `place_call` dials |
| `source` | `request_callback` | `twilio` or `simulated` |
| `step` | pipeline handlers | `created → placed → ringing → answered → asked → awaiting_last4 → verifying → done`; only ever advances |
| `attempts`, `answer_channel`, `digits`, `speech`, `speech_confidence`, `det_label` | `pipeline.on_first_answer` | `det_label` from `classify_answer` |
| `llm_label`, `llm_rationale` | Verifier (spec 005) | spoken answers only |
| `last4_ok` | `pipeline.on_last4` | 1, 0 or NULL |
| `final_label` | `pipeline._finalize` / supersede | CONFIRMED, DENIED, UNCLEAR, NO_ANSWER, LAST4_MISMATCH, VERIFIER_DISAGREED, SUPERSEDED |
| `events` | pipeline handlers | JSON timeline `[{ts, label, detail}]`; one "Answered" per call (research R5) |

## Token state (derived, `tokens.lookup`)

| State | Condition | Voice / answer / last4 | Status |
|---|---|---|---|
| `expired` | no row for the hash, or `expires_at` < now, or `final_label = SUPERSEDED` | "This verification line has expired." + Hangup | 204 |
| `final` | `final_label` set (not SUPERSEDED) | replay: DENIED → DENIED; CONFIRMED → L4_OK; else UNCLEAR; no state change | 204 |
| `active` | otherwise | call the pipeline | pipeline, then 204 |

## CallContext (PLAN.md §7.5, read-only here)

`verification_id, subject_id, kind, payer_name, counterparty_name, amount_cents, change_type, expected_last4, phone_to_call, attempts`, built by `pipeline.get_call_context`. Q1 is chosen from it:

- `kind = change_case` → "Q1, change case" with the change description (research R7)
- `change_type = bank_account` → "Q1, invoice bank change"
- otherwise → "Q1, invoice without a bank change"

## Webhook rejection (audit `webhook_rejected`)

`actor = "twilio"`, `subject_id = null`, `data = {route: "voice"|"answer"|"last4"|"status", reason: "bad_signature"|"no_auth_token", token_sha8}`. The token itself is never stored or logged.

## Outcome mapping (PLAN.md §12.5, implemented by spec 005)

| Final label | Invoice | Change case |
|---|---|---|
| DENIED | HELD(DENIED_BY_VENDOR) | DENIED |
| CONFIRMED | CONFIRMED (bank change applied if any), then the Payments agent | CONFIRMED |
| UNCLEAR | HELD(UNCLEAR_ANSWER) | UNCLEAR |
| LAST4_MISMATCH | HELD(LAST4_MISMATCH) | UNCLEAR |
| NO_ANSWER | HELD(NO_ANSWER) | NO_ANSWER |
| VERIFIER_DISAGREED | HELD(VERIFIER_DISAGREED) | UNCLEAR |
| SUPERSEDED | no transition | no change |
