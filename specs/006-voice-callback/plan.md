# Implementation Plan: Voice Callback Verification

**Branch**: `worktree-voice-callback` (spec directory `specs/006-voice-callback`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification and the Plan prompt in PLAN.md §23.6.

## Summary

Build the Twilio edge of the callback (PLAN.md §12) in `app/voice/`: place and cancel calls to the number on file (§12.1); four `/twilio/*` webhooks that authenticate every request (signature against `PUBLIC_BASE_URL`, hashed one-time token, CallSid match) and answer in under a second (§12.2); TwiML with the §12.3 gather settings and scripts word for word; and the pure §12.4 classifier. The §12.5 decision logic and the §7.5 pipeline functions already exist in `app/pipeline.py` (spec 005, merged at 451ac4b), so the routes are thin: read the form, check, `run_in_threadpool(pipeline.…)`, and render the script for the decision. `app/voice_port.py` already delegates to `app.voice.twilio_client` and `app.voice.classify` once they exist, so the pipeline needs no rewiring. `VOICE_MODE=simulated` stays the default; the B2 spike is removed.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: `twilio==9.11.2` (`Client`, `RequestValidator`, `VoiceResponse`, `Gather`), FastAPI 0.143 (`run_in_threadpool`), python-multipart (form parsing). All already pinned in `requirements.txt`.

**Storage**: SQLite `verifications` table (PLAN.md §7.2, frozen; spec 003 schema unchanged). Only the token's sha256 is stored.

**Testing**: pytest + FastAPI `TestClient`; signatures built with `RequestValidator.compute_signature` and a fake auth token set per test; `twilio.rest.Client` monkeypatched; inline executors by default, real pools for the timing test. No network, zero credentials (constitution V, VIII).

**Target Platform**: the Chicago VM behind Caddy (`/twilio/*` without basic auth, spec 002) and laptops in simulated mode.

**Project Type**: the existing single Python package. New: `app/voice/{classify,twiml,tokens,security,routes,twilio_client}.py`. Edited: `app/main.py` (mount the voice router, drop the spike), `app/pipeline.py` (two small changes, research R5/R10), `scripts/probe_edge.sh`.

**Performance Goals**: every webhook < 1 s (SC-005); phone rings ≤ 15 s after the click (SC-001; the B2 spike measured ringing at 1.1–1.7 s after `calls.create`); HELD(NO_ANSWER) ≈ 35 s on no answer (25 s ring timeout, SC-003).

**Constraints**: never call an LLM on a webhook path; never dial a number from an email; fail closed when the auth token is missing or the signature/token/CallSid does not check out; frozen §7 contracts and `schema.sql`, `models.py`, `state.py` untouched; §12.5 logic stays in `app/pipeline.py` (owner A), not duplicated in `app/voice/`.

**Scale/Scope**: 6 new modules, 3 PLAN.md test files plus 2 supporting test files, 4 HTTP routes.

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. PLAN.md source of truth | §12.1 call parameters, §12.2 check order, §12.3 gather settings and scripts, §12.4 patterns copied verbatim into contracts; §7.5 signatures unchanged | PASS |
| II. AI explains, code holds keys | classifier is deterministic; no model on any webhook; the Verifier (spec 005) can only downgrade a spoken yes | PASS |
| III. Fail closed | bad/missing signature or empty auth token → 403; unknown/expired/superseded token → expiry TwiML; CallSid mismatch → not acted on; place-call error → HELD(CALL_FAILED); silence → UNCLEAR | PASS |
| IV. Number on file | `place_call` receives only `phone_called` from the verification row (vendor `phone_on_file` or `DEMO_VENDOR_PHONE`), set by `request_callback` | PASS |
| V. Never blocked by setup | `VOICE_MODE=simulated` default; tests fake the auth token and the Twilio client | PASS |
| VI. Secrets stay in .env | auth token read from settings only; tokens never logged (hash prefix only) | PASS |
| VII. Evidence everywhere | `webhook_rejected`, `call_status`, `answer_received`, `last4_checked`, `verification_final` audit events; timeline events per step | PASS |
| VIII. Test the deterministic | the §12.4 table, signature/token/CallSid checks, and every §17.1 voice-flow row | PASS |
| IX. Designed for users | scripts word for word; neutral L4_OK so a later Verifier downgrade never contradicts what the vendor heard | PASS |
| X. Small slices | five phases, each stops and reports | PASS |
| XI. Fresh code | all new; the spike is deleted, not reused | PASS |

Post-design re-check: no violations.

## Project Structure

```text
specs/006-voice-callback/
├── plan.md, research.md, data-model.md, quickstart.md, tasks.md
└── contracts/ twilio-routes.md, scripts.md, interfaces.md

app/voice/
├── classify.py        # §12.4 classify_answer(digits, speech), pure
├── twiml.py           # §12.3 scripts and gathers; spoken amounts; q1_text(ctx); decision → TwiML
├── tokens.py          # sha256 lookup of a URL token → (verification, state); CallSid match/store
├── security.py        # signature check against PUBLIC_BASE_URL + path + query; webhook_rejected audit
├── routes.py          # APIRouter /twilio: voice, answer, last4, status (async read → run_in_threadpool)
└── twilio_client.py   # §12.1 place_call, best-effort cancel_call

app/main.py            # include the voice router before the static mount; spike removed
app/pipeline.py        # question_text → twiml.q1_text (R10); timeline event only when the step advances (R5)
scripts/probe_edge.sh  # probe /twilio/status/<random> → 403 instead of the spike route

tests/
├── test_classify.py         # §12.4 table (PLAN.md §17.1)
├── test_twiml.py            # scripts verbatim, gather settings, amount wording
├── test_twilio_security.py  # signature pass/403, expired token, superseded, CallSid (PLAN.md §17.1)
├── test_voice_flow.py       # every §17.1 voice-flow row through the routes and simulate_answer
└── test_twilio_client.py    # place_call parameters, cancel never raises (Client faked)

removed: app/voice/spike.py, tests/test_voice_spike.py, scripts/twilio_spike.py
```

**Structure Decision**: PLAN.md §6 lists `twilio_client.py, routes.py, twiml.py, tokens.py, classify.py` under `app/voice/`; this plan adds `security.py` to keep the signature check separately testable. No new top-level packages.

## Phases

1. **Classifier and scripts (pure)**: `classify.py`, `twiml.py`; `test_classify.py`, `test_twiml.py`. Milestone B3 gate, part 1.
2. **Webhook security and the router**: `tokens.py`, `security.py`, `routes.py` with the §12.2 check order; mount it in `main.py`; remove the spike; `test_twilio_security.py`. Milestone B3 gate, part 2.
3. **The flow through the webhooks**: decision → script mapping, CallSid store, idempotent replays, the "Answered" event, `question_text` from the real Q1, the < 1 s and no-LLM guarantees; `test_voice_flow.py` covering every §17.1 row.
4. **Placing real calls**: `twilio_client.py` (§12.1 verbatim, cancel best-effort), `voice_port` delegation checked, `probe_edge.sh` updated; `test_twilio_client.py`.
5. **Live phase and hand-off**: on the VM with `VOICE_MODE=twilio` and spec 002's public URL, place the fraud call ("no" → HELD) and the Heartland call (press 1, then 4455 → RELEASED); record timings in `docs/decisions.md`; `docs/voice.md`; quickstart validation; `/speckit-converge`; merge.

## Complexity Tracking

No constitution violations to justify.
