---

description: "Task list for spec 006: Voice Callback Verification"
---

# Tasks: Voice Callback Verification

**Input**: Design documents from `specs/006-voice-callback/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: spec 005 merged (451ac4b): `app/pipeline.py` implements PLAN.md §7.5 and §12.5; `app/voice_port.py` delegates to `app.voice.twilio_client` and `app.voice.classify` once they exist.

**Tests**: Requested (PLAN.md §17.1: `test_classify.py`, `test_twilio_security.py`, `test_voice_flow.py`; plus `test_twiml.py` and `test_twilio_client.py`). Tests come first in every phase and must fail before the code exists. No network, zero credentials: tests set a fake `TWILIO_AUTH_TOKEN` with `monkeypatch.setenv` + `config.reload()` and fake `twilio.rest.Client`.

**Organization**: phases follow plan.md "Phases"; each task carries the user story it serves.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 number-on-file call and "no" holds · US2 authenticated, idempotent, fast webhooks · US3 simulated mode · US4 last four and the Verifier · US5 retries, supersede, change cases

## Path Conventions

Single project: `app/`, `tests/`, `scripts/`, `docs/` at the repository root. New code lives in `app/voice/`. Never edit `app/schema.sql`, `app/models.py` or `app/state.py` (frozen, PLAN.md §7).

---

## Phase 1: Classifier and scripts (pure)

**Purpose**: the deterministic pieces every webhook needs: the §12.4 classifier and the §12.3 TwiML. No I/O.

**Independent Test**: `pytest tests/test_classify.py tests/test_twiml.py` with nothing configured.

- [x] T001 [P] [US1] Create `tests/test_classify.py`: every row of the PLAN.md §12.4 table (contracts/scripts.md) as a parametrized case against `app.voice.classify.classify_answer(digits, speech)`: "No, we never changed banks" NO; "nope that wasn't us" NO; "Yes we did" YES; "yeah that's right" YES; "yeah that's right we didn't change anything" UNCLEAR; "I don't know" NO; "That's not correct" UNCLEAR; "No." NO; "" UNCLEAR; digits "1" YES; digits "9" UNCLEAR. Add: digits "2" → NO; digits win over speech (`("1", "no")` → YES); curly quotes and line breaks normalize ("that wasn’t\nus" → NO); `None, None` → UNCLEAR; and `app.voice_port.classify_answer` now returns the real classifier's answer for speech ("Yes we did" → YES)
- [x] T002 [P] [US1] Create `tests/test_twiml.py`: each script in contracts/scripts.md is produced word for word (compare full strings with payer "Northgate Manufacturing", counterparty "Acme Supply Co.", amount 4875000 cents); `spoken_amount(4875000)` == "48,750 dollars", `spoken_amount(412050)` == "4,120 dollars and 50 cents", `spoken_amount(None)` == "the requested amount"; Q1 selection from a `CallContext` (bank_account → "Q1, invoice bank change"; other invoice change types → "Q1, invoice without a bank change"; kind change_case → "Q1, change case" with "billing contact" for `billing_contact`); the DENIED change-case variant says "make this change"; the first Gather renders `input="dtmf speech"`, `numDigits="1"`, `timeout="7"`, `speechTimeout="auto"`, the exact hints, `actionOnEmptyResult="true"`, `language="en-US"`, `action="<PUBLIC_BASE_URL>/twilio/answer/<token>?n=<attempt>"` (attempt 1 for Q1, 2 for the reprompt; analyze U1), `method="POST"`; the last-four Gather renders `input="dtmf"`, `numDigits="4"`, `timeout="10"`, `finishOnKey="#"`, action `/twilio/last4/<token>` and is followed by a POST `<Redirect>` to the same URL (research R6); every `<Say>` uses `voice="Polly.Joanna-Neural"`; the expiry response is `<Say>This verification line has expired.</Say><Hangup/>`; each decision in research R8 maps to its script, and every terminal script ends with `<Hangup/>`
- [x] T003 [P] [US1] Create `app/voice/classify.py`: `classify_answer(digits: str | None, speech: str | None) -> Literal["YES", "NO", "UNCLEAR"]`, pure, check order and the NO/YES patterns exactly as PLAN.md §12.4 (contracts/scripts.md), speech normalized with `core.phrases.normalize`; "NO only → NO. YES only → YES. Both or neither → UNCLEAR."
- [x] T004 [P] [US1] Create `app/voice/twiml.py` (pure; imports nothing from `app.pipeline`): constants `VOICE = "Polly.Joanna-Neural"`, `VOICE_FALLBACK = "Polly.Joanna"`; every §12.3 script as a constant or `format` function; `spoken_amount(cents)` and the change descriptions of research R7; `q1_text(ctx: CallContext) -> str`; `first_gather(token, text, attempt)` (action `/twilio/answer/{token}?n={attempt}`, analyze U1), `last4_gather(token, text)`; `for_first_answer(decision, ctx, token)`, `for_last4(decision)`, `for_final(final_label, ctx)` (replay map: DENIED → DENIED, CONFIRMED → L4_OK, else UNCLEAR), `expired()`, each returning the TwiML string; URLs built from `config.S.public_base_url`

**Checkpoint**: run `pytest -q`; commit "spec 006 phase 1"; stop and report.

---

## Phase 2: Webhook security and the router

**Purpose**: every `/twilio/*` request proves it came from Twilio and names a live verification before anything happens (PLAN.md §12.2). Removes the B2 spike.

**Independent Test**: `pytest tests/test_twilio_security.py` with a fake auth token.

- [x] T005 [US2] Create `tests/test_twilio_security.py` with a `signed(client, path, params, token=AUTH)` helper that builds `X-Twilio-Signature` via `RequestValidator(AUTH).compute_signature(PUBLIC_BASE_URL + path, params)`, and a fixture that sets `TWILIO_AUTH_TOKEN`, `PUBLIC_BASE_URL=https://cmb.test`, `VOICE_MODE=simulated`, reloads config and creates a fraud invoice in CALLING with a known token (create the verification with `app.verifications.create` and keep the returned token). Cases: a correctly signed voice request → 200 TwiML containing Q1; a tampered param, a wrong token in the signature, a missing header, and a signature computed for `http://app:8000/...` (the URL the app sees behind Caddy) → 403, audit `webhook_rejected` with actor `twilio` and `reason`, no change to the verification or invoice; with `TWILIO_AUTH_TOKEN` empty every request → 403 even with a "valid" header; an unknown token → expiry TwiML; an expired token (`expires_at` set in the past) → expiry TwiML and no state change; a SUPERSEDED verification → expiry TwiML; the status route answers 204 for unknown/expired tokens; a query string is part of the signed URL; `TWILIO_VALIDATE_SIGNATURE=0` with `VOICE_MODE=simulated` accepts an unsigned request, but with `VOICE_MODE=twilio` (any `DEMO_MODE`) the signature is still required (research R3, analyze C1); the uvicorn access-log filter rewrites `/twilio/voice/<token>` to `/twilio/voice/…<sha8>` so the token never reaches a log line (analyze D1); the token never appears in the audit data (only `token_sha8`)
- [x] T006 [P] [US2] Create `app/voice/tokens.py`: `new_token` re-exported from `app.verifications` (PLAN.md §7.5); `hash_token(token) -> sha256 hex`; `lookup(token) -> tuple[dict | None, Literal["active", "final", "expired"]]` per data-model.md "Token state" (unknown, `expires_at` < now, or `final_label = SUPERSEDED` → expired; other final labels → final; else active), selecting `verifications` by `token_hash`; `match_call(ver, call_sid) -> bool` that stores `call_sid` when none is stored and returns False on a mismatch (research R5)
- [x] T007 [P] [US2] Create `app/voice/security.py`: `signed_url(request) = S.public_base_url + request.url.path + ("?" + request.url.query if request.url.query else "")`; `is_valid(request, form) -> tuple[bool, str]` using `RequestValidator(S.twilio_auth_token).validate(url, dict(form), request.headers.get("X-Twilio-Signature", ""))`; empty auth token → `(False, "no_auth_token")`; the `TWILIO_VALIDATE_SIGNATURE=0` rule of research R3: honored only when `VOICE_MODE=simulated` (warning per request), ignored with a warning when `VOICE_MODE=twilio` (analyze C1); `install_access_log_redaction()` adding an idempotent `logging.Filter` to the `uvicorn.access` logger that rewrites any `/twilio/<route>/<token>` in the record args to `/twilio/<route>/…<sha8>` (analyze D1); `reject(route, token, reason)` writes audit `webhook_rejected` (actor `twilio`, subject null, data `{route, reason, token_sha8}`) and returns `Response(status_code=403)`
- [x] T008 [US2] Create `app/voice/routes.py`: `router = APIRouter(prefix="/twilio")` with `POST /voice/{token}`, `/answer/{token}`, `/last4/{token}`, `/status/{token}`; each is `async def`: `form = await request.form()`, signature check (403 path awaits `run_in_threadpool(security.reject, …)`), then a single `await run_in_threadpool(_handle_<route>, token, dict(form))` that does `tokens.lookup`, `tokens.match_call` and the pipeline call, and returns TwiML text (or None for 204); TwiML responses use `media_type="application/xml"`; expired/mismatched → `twiml.expired()`; final → `twiml.for_final(...)`; Phase 2 wires `voice` to `pipeline.on_call_status(id, "in-progress")` + `get_call_context` + Q1, and `status` to `pipeline.on_call_status(id, CallStatus)` → 204; depends on T004, T006, T007
- [x] T009 [US2] Edit `app/main.py`: include `app.voice.routes.router` (always, both voice modes) before the static mount; call `security.install_access_log_redaction()` at startup; remove the DEMO_MODE spike include; delete `app/voice/spike.py`, `tests/test_voice_spike.py` and `scripts/twilio_spike.py` (research R11); keep `/healthz`, the API router and the "no SPA fallback" note

**Checkpoint**: `pytest -q` green (the spike tests are gone, `test_main_healthz.py` still passes); commit "spec 006 phase 2"; stop and report.

---

## Phase 3: The flow through the webhooks

**Purpose**: the answer, last-four and status webhooks drive spec 005's §12.5 logic and speak the right script; replays change nothing; the phone never waits on a model.

**Independent Test**: `pytest tests/test_voice_flow.py`.

- [ ] T010 [US1] Create `tests/test_voice_flow.py` reusing the signing helper (move it to `tests/twilio_helpers.py` and import it from both files), driving signed webhooks with `CallSid="CA_test"` against invoices put in CALLING by `pipeline.submit_invoice` (simulated mode creates the verification; read its token by creating a fresh verification through `pipeline.request_callback` with `voice_port.place_call` monkeypatched to record the token and return `"CA_test"` and `VOICE_MODE=twilio`). Every PLAN.md §17.1 row: fraud + webhook "No, we never changed banks" (and separately digits "2") → DENIED script and HELD(DENIED_BY_VENDOR); Heartland + digits "1" → ASK_LAST4 gather, then last4 "4455" → L4_OK, RELEASED, payment to ••••4455 and vendor master "Gateway National Bank"; Heartland + "1" + "1111" → L4_BAD and HELD(LAST4_MISMATCH); status "no-answer" → 204 and HELD(NO_ANSWER); a duplicated answer webhook → the same TwiML, no extra `status_changed` audit row and the invoice `version` unchanged (SC-004); simulate while a live (twilio-source) verification is active → the old one is SUPERSEDED, `voice_port.cancel_call` got its CallSid, and a later voice/answer webhook on its token hears the expiry message with no change; "completed" while `verifying` (spoken yes + 4455, `await_verifier` held off) → no hold; a spoken "yes we did" with AI off → after the last four, HELD(VERIFIER_DISAGREED). Also: an UNCLEAR first answer → REPROMPT inside the first Gather, a second → UNCLEAR script and HELD(UNCLEAR_ANSWER); silence on the last four (empty Digits via the redirect) → UNCLEAR script and HELD(UNCLEAR_ANSWER); a webhook with a different CallSid → expiry TwiML and no change; a replayed answer webhook after a REPROMPT (same `?n=1`) re-renders the REPROMPT gather and does **not** count as the second attempt, while `?n=2` does (analyze U1); a retried ringing or in-progress status callback, and the voice fetch followed by Twilio's own in-progress callback, add no extra `call_status` audit row or timeline event, and a duplicated `completed` audits once (analyze I1, SC-004); a HELD(NO_ANSWER) invoice retried through `pipeline.retry_callback` gets a new verification whose fresh token works through the webhooks, while the old token hears the expiry message (analyze E1, US5 AC1); a final verification's retried answer webhook replays DENIED/L4_OK/UNCLEAR; the voice fetch plus the `in-progress` status callback write exactly one "Answered" timeline event (research R5); the `verifier_label` prompt received the exact Q1 text (research R10); a change case through the webhooks reads "Q1, change case", a "no" hears "make this change" and sets only `change_cases.status` (US5); every route answers in < 1 s; with AI live, real thread pools and a Verifier model that sleeps 5 s, a spoken answer webhook answers in < 1 s before the model returns (research R12, SC-005)
- [ ] T011 [US1] In `app/voice/routes.py` complete `answer`: `decision = pipeline.on_first_answer(id, Digits or None, SpeechResult or None, float(Confidence) if Confidence else None)` and render `twiml.for_first_answer(decision, ctx, token)`, after the replay check: when the query `n` is at or below the stored `attempts`, skip the pipeline and re-render the prompt for the current step (research R8, analyze U1); `last4`: `pipeline.on_last4(id, Digits or None)` → `twiml.for_last4(decision)`; empty strings become None (contracts/twilio-routes.md)
- [ ] T012 [US4] Edit `app/pipeline.py`: `question_text(ctx)` returns `app.voice.twiml.q1_text(ctx)` (research R10; signature unchanged); `on_call_status` writes the `call_status` audit row and the timeline event for queued/initiated/ringing/in-progress only when it advances the step, and handles `completed` once per verification (a "Call completed" timeline marker; later duplicates neither audit nor schedule another grace check) (research R5, analyze I1); run spec 005's tests unchanged to prove nothing else moved
- [ ] T013 [US3] In `tests/test_voice_flow.py` add the simulated-mode rows through the API: `VOICE_MODE=simulated` → `request_callback` places no call, the verification `source` is `simulated`, the timeline has "Simulated line: answer with the demo controls"; `POST /api/demo/simulate-answer` "no" → HELD(DENIED_BY_VENDOR) with actor `demo` and `"simulated": true` on every audit entry of the voice path; `DEMO_MODE=0` → 404 from the demo route and a CONFIRMED invoice with a simulated verification is not releasable (`ledger.can_release` false, PLAN.md §13.1)

**Checkpoint**: `pytest -q`; commit "spec 006 phase 3"; stop and report.

---

## Phase 4: Placing real calls

**Purpose**: the pipeline's `request_callback` dials the number on file through Twilio when `VOICE_MODE=twilio`.

**Independent Test**: `pytest tests/test_twilio_client.py` with a fake `Client`.

- [ ] T014 [P] [US1] Create `tests/test_twilio_client.py` with a fake `twilio.rest.Client` (monkeypatched in `app.voice.twilio_client`) that records arguments: `place_call("ver_x", "tok", "+18165550199")` calls `calls.create` with exactly the PLAN.md §12.1 arguments (`to`, `from_=TWILIO_FROM_NUMBER`, `url=PUBLIC_BASE_URL/twilio/voice/tok`, `method="POST"`, `status_callback=PUBLIC_BASE_URL/twilio/status/tok`, `status_callback_event=["initiated", "ringing", "answered", "completed"]`, `status_callback_method="POST"`, `timeout=25`) and returns the SID; `cancel_call("CA1")` calls `calls("CA1").update(status="completed")` and returns None when the client raises; through the pipeline with `VOICE_MODE=twilio`: `request_callback` on the fraud invoice dials `vendor.phone_on_file` (never the "(816) 555-0142" in the email), stores the SID and moves to CALLING; a `calls.create` exception → HELD(CALL_FAILED) with a memo; `voice_port.place_call` and `voice_port.cancel_call` now reach this module
- [ ] T015 [P] [US1] Create `app/voice/twilio_client.py`: `place_call(verification_id, token, to_e164) -> str` exactly as PLAN.md §12.1 (Client per call from settings); `cancel_call(call_sid) -> None` doing `client.calls(call_sid).update(status="completed")` inside try/except with a warning log ("never raises", §7.5)
- [ ] T016 [US1] Edit `scripts/probe_edge.sh`: replace the `/twilio/spike/status` probe with an unsigned POST to `/twilio/status/probe-<random>` expecting 403 from the app (proves Caddy forwards `/twilio/*` without basic auth and the signature check is live); update the expected-results comment

**Checkpoint**: `pytest -q`; commit "spec 006 phase 4"; stop and report.

---

## Phase 5: Live phase on the VM and hand-off

**Purpose**: prove the real phone path (milestone B5) and hand off.

- [ ] T017 [US1] Live check on the VM (manual, needs spec 002's public URL and the Twilio variables in the VM's `.env`; never print them): `VOICE_MODE=twilio`; `scripts/probe_edge.sh`; run quickstart.md §3 steps 3–5 (fraud "no" → HELD(DENIED_BY_VENDOR); Heartland press 1 + 4455# → RELEASED to ••••4455; no answer → HELD(NO_ANSWER)); record ring time, answer-to-HELD time and any 11200/403 in `docs/decisions.md`; if Twilio rejects `Polly.Joanna-Neural`, switch `twiml.VOICE` to `VOICE_FALLBACK` and note it
- [ ] T018 [P] Write `docs/voice.md` (≤ 50 lines): the four routes and their check order, the scripts' source (contracts/scripts.md), simulated vs twilio mode, the signature URL rule and the 403 fix (PLAN.md §16.5), how to switch the voice, and how a webhook reaches `app/pipeline.py`
- [ ] T019 [P] Run `specs/006-voice-callback/quickstart.md` §1–§2 on a fresh database and fix anything that does not match its expected results
- [ ] T020 Run `/speckit-converge` until it reports converged, then rebase on `origin/main`, run the full `pytest -q`, push, fast-forward `main`, and remove the worktree when asked (PLAN.md §0.5 step 6)

---

## Dependencies & Execution Order

- **Phase 1** has no dependencies; T001/T002 (tests) before T003/T004.
- **Phase 2** depends on Phase 1 (routes render `twiml`); T005 first; T006 and T007 in parallel; T008 after both; T009 after T008.
- **Phase 3** depends on Phase 2; T010 first; T011 and T012 touch different files and can run in parallel; T013 last.
- **Phase 4** depends on Phase 2 (the routes Twilio calls back); independent of Phase 3 except that T014's CALL_FAILED memo row relies on spec 005's FR-006 fix (already merged).
- **Phase 5** depends on Phases 1–4 and on spec 002's live URL for T017.
- **Stories**: US1 spans Phases 1, 3, 4; US2 is Phase 2; US3 and US4 are verified in Phase 3 (their logic is spec 005's); US5 rows (supersede, change case) are in T010, retry is spec 005's and covered there.

## Parallel Example: Phase 1

```text
T001 tests/test_classify.py      T002 tests/test_twiml.py
T003 app/voice/classify.py       T004 app/voice/twiml.py
```

## Parallel Example: Phase 2

```text
T006 app/voice/tokens.py         T007 app/voice/security.py
```

## Implementation Strategy

- **MVP (US1 + US2, milestone B3)**: Phases 1–3 in simulated mode: the classifier, the scripts, secure webhooks and the full flow driven by signed requests in tests. This is what PLAN.md §18 gates B3 on (`test_classify.py` and `test_twilio_security.py` green).
- **Live (milestone B5)**: Phase 4 then T017 on the VM; the checkpoint is a real fraud call that ends HELD.
- One phase at a time; after each, run `pytest -q`, commit, stop and report (constitution X).

## Notes

- `app/voice/` holds no §12.5 decision logic; if a test needs a decision changed, the change belongs in `app/pipeline.py` and spec 005's tests must stay green.
- Tests never call the network: the Twilio `Client` is faked and signatures are computed locally.
- Never log or store a raw token; audit data carries `token_sha8` only.
