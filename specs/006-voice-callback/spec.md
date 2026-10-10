# Feature Specification: Voice Callback Verification

**Feature Branch**: `006-voice-callback`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Phone verification for Call Me Back. When policy requires it, call the vendor at the number on file, never a number from the email. Ask whether they requested the change and accept a spoken or keypad answer. For a bank change, also ask for the last four digits of the new account.
A clear yes, with matching digits, confirms. A no, silence, a hang-up, a mismatch or an unclear answer holds the payment.
P1: Webhooks are authenticated and idempotent, never wait on AI, and answer within a second.
P1: Without phone credentials, the same flow runs in a simulated mode with demo buttons.
P2: Retries, superseding a call that's still ringing, and a change-case script for DevRev.
Details are in PLAN.md §12."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The vendor is called at the number on file and a "no" holds the payment (Priority: P1)

An invoice is routed RED or carries a bank change, so the pipeline requests a callback. The system places one call to the vendor's `phone_on_file` from the vendor master (PLAN.md §12.1; never a number from the email, per PLAN.md §1 principle 3). When the vendor answers, the line reads the matching Q1 script word for word (PLAN.md §12.3) and listens for a spoken or keypad answer. A deterministic classifier (PLAN.md §12.4) turns the answer into YES, NO or UNCLEAR, and the pipeline decision logic (PLAN.md §12.5) applies the outcome. On stage this is the P0 spine: the fraud sample, a real phone ringing, the vendor saying "No, we never changed banks", and the invoice HELD with reason DENIED_BY_VENDOR.

**Why this priority**: PLAN.md §4 lists "RED → live call → vendor says no → HELD" as P0 and "the live call" as never-cut. It is the moment the product's name comes true.

**Independent Test**: Against pipeline stubs in simulated mode, drive the handlers directly: `on_first_answer` with digits "2" or speech "No, we never changed banks" ends in HELD(DENIED_BY_VENDOR) with the DENIED script, and every row of the §12.4 classifier table returns its expected label (`test_classify.py`, `test_voice_flow.py`, PLAN.md §17.1). Once spec 002's public URL and the telephony account are live, the same test is a real call to Builder B's phone.

**Acceptance Scenarios**:

1. **Given** a RED invoice whose vendor has a phone on file and whose email names a different number, **When** the callback is requested, **Then** exactly one call goes to the number on file and the email's number is never dialed.
2. **Given** the call is answered on a bank-change invoice, **When** the line speaks, **Then** it reads the "Q1, invoice bank change" script verbatim with payer, counterparty and amount filled in, and amounts are spoken as "48,750 dollars" (PLAN.md §12.3).
3. **Given** an answered call on a RED or lookalike invoice with the bank on file unchanged, **When** the line speaks, **Then** it reads the "Q1, invoice without a bank change" script.
4. **Given** Q1 has been asked, **When** the vendor presses 2 or says "no", **Then** the vendor hears the DENIED script, the verification is final with label DENIED, the invoice is HELD(DENIED_BY_VENDOR), and the Payments agent is started for the memo (PLAN.md §12.5).
5. **Given** the classifier (PLAN.md §12.4), **When** it receives each input below, **Then** it returns the expected label:

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

6. **Given** the first answer is UNCLEAR, **When** the pipeline decides, **Then** the vendor hears the REPROMPT script with the same answer prompt; **Given** a second UNCLEAR answer, **Then** the vendor hears the UNCLEAR script and the invoice is HELD(UNCLEAR_ANSWER).
7. **Given** the call is ringing, **When** the telephony provider reports busy, no-answer, failed or canceled, **Then** the invoice is HELD(NO_ANSWER); **When** it reports completed while the verification step is still at or before `awaiting_last4`, **Then** after the 3 s grace re-read it is HELD(UNCLEAR_ANSWER) (PLAN.md §12.5 `on_call_status`).

---

### User Story 2 - Webhooks are authenticated, idempotent, fast and never wait on AI (Priority: P1)

The telephony provider fetches the voice, answer, last-4 and status webhooks on a public URL that carries no basic auth (spec 002). Each request must prove it came from the provider, must name a live verification through a one-time token, and must be safe to replay, because providers retry. Every webhook answers in under 1 second and never calls a language model, so there is never dead air on the phone (PLAN.md §12.2).

**Why this priority**: A webhook anyone can post to is a way to "confirm" a fraudulent payment from a laptop, which is the attack this product exists to stop (constitution II, III). PLAN.md §12.2 applies to every voice route and milestone B3 (PLAN.md §18) gates on `test_twilio_security.py`.

**Independent Test**: `test_twilio_security.py` (PLAN.md §17.1): a correctly signed form passes, a tampered one returns 403 and writes audit `webhook_rejected`, and an expired token returns the expiry message. `test_voice_flow.py`: a duplicated answer webhook causes zero extra transitions.

**Acceptance Scenarios**:

1. **Given** any `/twilio/*` route, **When** the request's signature does not validate against the public base URL plus path and query (PLAN.md §12.2 step 2), **Then** the response is HTTP 403 and an audit event `webhook_rejected` is written; no state changes.
2. **Given** a token that is unknown, expired (older than 15 minutes) or belongs to a SUPERSEDED verification, **When** a voice, answer or last-4 webhook arrives, **Then** the caller hears "This verification line has expired." and the call ends; the status route returns 204 instead.
3. **Given** a verification that is already final, **When** a retried webhook arrives, **Then** nothing changes and the script matching its `final_label` is replayed (DENIED → DENIED, CONFIRMED → L4_OK, anything else → UNCLEAR).
4. **Given** the same answer webhook is delivered twice, **When** both are processed, **Then** the second causes no additional transition, audit `status_changed` event or agent start.
5. **Given** a webhook whose CallSid differs from the stored `call_sid`, **When** it is checked, **Then** it is not acted on; **Given** no `call_sid` is stored yet (first-fetch race), **Then** the incoming one is stored.
6. **Given** any webhook, **When** it is served, **Then** it responds within 1 second and no language model is called on the request path; the Verifier runs in the background and the vendor hears the neutral L4_OK or CONFIRMED_NO_LAST4 script.

---

### User Story 3 - The same flow runs in simulated mode with demo buttons (Priority: P1)

With no phone credentials or public URL (`VOICE_MODE=simulated`, the default per PLAN.md §0.4), requesting a callback places no call. It creates a verification with `source="simulated"`, moves the invoice to CALLING and adds the timeline event "Simulated line: answer with the demo controls". In DEMO_MODE the operator presses Yes or No (with a last-4 field) and `simulate_answer` runs the identical decision logic (PLAN.md §12.6). The UI shows a SIMULATED badge, the audit actor is `demo`, and every entry carries `"simulated": true`.

**Why this priority**: Constitution V: implementation never waits on credentials, and the whole suite must pass with none. PLAN.md §4 lists "the simulate fallback" as never-cut; it is also the stage fallback when a phone does not ring.

**Independent Test**: With `VOICE_MODE=simulated` and `DEMO_MODE=1`, run the fraud sample to CALLING, call `simulate_answer(id, "no", None)` and observe HELD(DENIED_BY_VENDOR) with the same audit events a live call would write, each flagged simulated. With `DEMO_MODE=0`, a CONFIRMED invoice whose verification is simulated is not releasable (`test_ledger.py`, PLAN.md §13.1).

**Acceptance Scenarios**:

1. **Given** `VOICE_MODE=simulated`, **When** a callback is requested, **Then** no call is placed, a simulated verification exists, the invoice is CALLING and the timeline shows the simulated-line event.
2. **Given** DEMO_MODE is on and the invoice is CALL_PENDING or CALLING, **When** the operator answers "no", **Then** the invoice is HELD(DENIED_BY_VENDOR) through the same code path, with actor `demo` and `"simulated": true` on every audit entry, and the case shows a SIMULATED badge.
3. **Given** DEMO_MODE is off, or the invoice is in any other status than CALL_PENDING, CALLING or HELD with a retryable reason, **When** `simulate_answer` is requested, **Then** it returns 409 and nothing changes.
4. **Given** DEMO_MODE is off, **When** release eligibility is checked for a CONFIRMED invoice whose latest verification is simulated, **Then** release is refused (PLAN.md §13.1).

---

### User Story 4 - A bank change needs a matching last four, and a spoken yes needs the Verifier (Priority: P2)

For the Heartland bank-change sample, a "yes" is not enough. The line reads ASK_LAST4 and collects four keypad digits ending in `#`. Matching digits with a keypad "1" confirm the invoice; the vendor master is updated and the payment goes to the new account. Wrong digits hold the payment. A spoken "yes" is provisional: the invoice goes to VERIFYING while the Verifier agent reviews the transcript, and only its agreement confirms; anything else, including AI off or a timeout, holds (PLAN.md §12.5).

**Why this priority**: PLAN.md §4 P1: "Heartland bank change: yes plus last-4 4455 → CONFIRMED → released, and the vendor master is updated." It is the happy path that proves the product pays legitimate vendors.

**Independent Test**: `test_voice_flow.py` (PLAN.md §17.1): Heartland + yes + 4455 → RELEASED to ••••4455; Heartland + yes + 1111 → HELD(LAST4_MISMATCH); a spoken "yes we did" with AI off → HELD(VERIFIER_DISAGREED); "completed" arriving while `verifying` → no hold.

**Acceptance Scenarios**:

1. **Given** a bank-change invoice with an expected last four, **When** the vendor answers YES, **Then** the step becomes `awaiting_last4` and the vendor hears ASK_LAST4.
2. **Given** the vendor pressed 1, **When** they enter the matching four digits, **Then** `last4_ok` is set, the verification is final CONFIRMED, the invoice is CONFIRMED, the vendor bank change is applied and the Payments agent starts; the vendor hears the neutral L4_OK script.
3. **Given** the digits do not match (compared in constant time), **When** the pipeline decides, **Then** the vendor hears L4_BAD and the invoice is HELD(LAST4_MISMATCH); **Given** no digits arrive within the gather timeout, **Then** the vendor hears UNCLEAR and the invoice is HELD(UNCLEAR_ANSWER).
4. **Given** the YES was spoken (not keypad) and the last four match, **When** the pipeline decides, **Then** the vendor still hears L4_OK, the invoice moves to VERIFYING, and a background job waits for the Verifier up to `TIMEOUT_VERIFIER_S` + 5 s: CONFIRMED → invoice CONFIRMED (bank change applied, Payments agent started); anything else, missing or timed out → HELD(VERIFIER_DISAGREED).
5. **Given** a YES on an invoice with no expected last four, **When** it came by keypad, **Then** the invoice is CONFIRMED immediately; **When** it was spoken, **Then** it goes to VERIFYING and the Verifier decides; in both cases the vendor hears CONFIRMED_NO_LAST4.
6. **Given** the invoice is in VERIFYING, **When** the provider reports the call completed, **Then** only a timeline event is written and the Verifier job decides the outcome.

---

### User Story 5 - Retries, superseding a ringing call, and the change-case script (Priority: P3)

An operator can retry a callback from HELD with reason UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED or VERIFIER_DISAGREED (PLAN.md §7.3, §7.6). Requesting a callback or simulating an answer first marks any active verification SUPERSEDED, with no invoice transition, and hangs up its call if one is in flight; later webhooks for the old token change nothing (PLAN.md §12.5). For DevRev change cases, the same line reads the "Q1, change case" script to `DEMO_VENDOR_PHONE`, says "make this change" in the DENIED script, and finalizes `change_cases.status` without touching invoices or the ledger (PLAN.md §12.3, §12.5, §15).

**Why this priority**: Retry and supersede are the "call didn't ring on stage" recovery; the change-case call is PLAN.md §4 P2 ("Placing a sandbox call from a DevRev case").

**Independent Test**: `test_voice_flow.py`: simulate while a live verification is active → the old one is SUPERSEDED and its later webhooks change nothing. A HELD(NO_ANSWER) invoice retried reaches CALLING again with a new verification and a fresh token. A change case driven through the handlers ends with its own status set and no invoice or payment rows touched.

**Acceptance Scenarios**:

1. **Given** an invoice HELD with a retryable reason, **When** retry is requested, **Then** it moves HELD → CALL_PENDING → CALLING with a new verification; **Given** any other hold reason, **Then** the request is refused with 409.
2. **Given** a live verification is still ringing, **When** the operator simulates an answer, **Then** the old verification becomes SUPERSEDED, its call is cancelled best-effort, and a later webhook on its token hears the expiry message and changes nothing.
3. **Given** a change case callback, **When** the line is answered, **Then** it reads the change-case Q1 with the change description, and a "no" sets the case's status without any invoice or ledger change.

---

### Edge Cases

- The public base URL differs from the URL the provider signed (scheme, host, trailing slash): every webhook is 403 and the fix is configuration (PLAN.md §16.5), never relaxing the check.
- Placing the call raises (no balance, bad number, provider down): the invoice is HELD(CALL_FAILED) and can be retried (PLAN.md §7.5 `request_callback`).
- The answer and the hang-up arrive almost together: the completed handler waits 3 s and re-reads the row before deciding (PLAN.md §12.5).
- Speech contains both a yes and a no pattern, or neither: UNCLEAR, one reprompt, then hold. Keypad digits other than 1 or 2: UNCLEAR.
- "I don't know" classifies as NO and holds: fail closed is the intended behavior (PLAN.md §12.4).
- The neural voice is rejected by the provider: fall back to the standard voice; scripts are unchanged (PLAN.md §12.3).
- AI is off or the model times out: a spoken yes ends HELD(VERIFIER_DISAGREED); only keypad 1 can confirm, which is why rehearsal presses 1 (PLAN.md §12.5).
- A token is guessed: the database holds only its hash, tokens are 24 random bytes and expire after 15 minutes; unknown tokens get the expiry message.
- The phone does not ring on stage: supersede with the demo buttons (PLAN.md §12.6 step 2, §16.5).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST place verification calls only to the vendor's `phone_on_file` (or `DEMO_VENDOR_PHONE` for change cases) and MUST never dial a number taken from an email or request (PLAN.md §12.1, §1 principle 3).
- **FR-002**: Each verification MUST carry a one-time URL token; storage keeps only its hash and the token expires 15 minutes after creation (PLAN.md §12.1, §7.2).
- **FR-003**: Every voice webhook MUST validate the provider signature against the public base URL, path and query; failures return 403 and write audit `webhook_rejected` (PLAN.md §12.2).
- **FR-004**: Every voice webhook MUST be token-scoped: unknown, expired or SUPERSEDED tokens receive the expiry message (204 on the status route); final verifications replay the script for their `final_label` and change nothing (PLAN.md §12.2).
- **FR-005**: Every state change MUST go through `transition()` and the verification `step`, so a repeated webhook is a no-op; the CallSid MUST match the stored one, or be stored if absent (PLAN.md §12.2, §7.3).
- **FR-006**: Every voice webhook MUST respond within 1 second and MUST NOT call a language model (PLAN.md §12.2).
- **FR-007**: The system MUST expose exactly the four routes in PLAN.md §12.3 (voice, answer, last4, status) with the gather settings given there, and MUST speak the scripts of PLAN.md §12.3 word for word.
- **FR-008**: The answer classifier MUST be pure and deterministic, apply the check order and patterns of PLAN.md §12.4, and pass the full test table.
- **FR-009**: Outcomes MUST follow PLAN.md §12.5: no → HELD(DENIED_BY_VENDOR); yes with matching last four → CONFIRMED; yes with wrong last four → HELD(LAST4_MISMATCH); silence or unclear twice → HELD(UNCLEAR_ANSWER); no answer, busy, failed or canceled → HELD(NO_ANSWER); spoken yes without Verifier agreement → HELD(VERIFIER_DISAGREED); keypad 1 confirms without the Verifier.
- **FR-010**: A spoken "yes" MAY be downgraded by the Verifier and MUST never be upgraded by it; a NO or UNCLEAR from the classifier is never overridden by a model (PLAN.md §12.5, constitution II).
- **FR-011**: A confirmed bank change MUST set `last4_ok`, apply the vendor bank change, and only then start the Payments agent (PLAN.md §12.5, §13.1).
- **FR-012**: The last-four comparison MUST use a constant-time comparison (PLAN.md §12.5).
- **FR-013**: Status callbacks MUST advance the step for queued/initiated/ringing/in-progress, hold on busy/no-answer/failed/canceled, and on completed wait 3 s then decide by step (PLAN.md §12.5).
- **FR-014**: Requesting a callback or simulating an answer MUST first mark any active verification SUPERSEDED with no invoice transition and cancel its call best-effort; cancellation never raises (PLAN.md §12.5, §7.5).
- **FR-015**: In `VOICE_MODE=simulated` the system MUST place no call, create a `source="simulated"` verification, move the invoice to CALLING and add the simulated-line timeline event; all other logic is identical (PLAN.md §12.6).
- **FR-016**: `simulate_answer` MUST be available only in DEMO_MODE and only from CALL_PENDING, CALLING or HELD with a retryable reason (moving HELD → CALL_PENDING first); otherwise 409. It uses the same code path with actor `demo`, `"simulated": true` on every audit entry, and a SIMULATED badge in the UI (PLAN.md §12.6).
- **FR-017**: Release eligibility MUST accept `source="simulated"` only when DEMO_MODE is on (PLAN.md §13.1).
- **FR-018**: Every decision MUST write audit and timeline events, and masked values only (last four digits) appear outside the database (PLAN.md §7.2, §13.3, constitution VII).
- **FR-019**: Change-case verifications MUST use the change-case scripts and finalize `change_cases.status` without touching invoices or the ledger (PLAN.md §12.3, §12.5).
- **FR-020**: Retry MUST be allowed only from HELD with UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED or VERIFIER_DISAGREED (PLAN.md §7.3, §7.6).
- **FR-021**: `test_classify.py`, `test_twilio_security.py` and `test_voice_flow.py` MUST cover the rows in PLAN.md §17.1 and MUST pass with zero credentials and no network.

### Key Entities

- **Verification**: one attempt to confirm a subject (invoice or change case) by phone; carries kind, token hash, expiry, call id, phone called, source (`twilio` | `simulated`), step, attempts, answer channel, digits, speech and confidence, deterministic label, Verifier label and rationale, `last4_ok`, final label, and a JSON timeline (PLAN.md §7.2).
- **Call Context**: what the line needs to speak and decide: payer, counterparty, spoken amount, whether a last four is expected and what it is, and the subject kind (PLAN.md §7.5 `get_call_context`).
- **Verification Token**: a 24-byte random URL token known only to the provider and the running call; stored as a hash; the unit of webhook scope (PLAN.md §12.1).
- **Final Label**: CONFIRMED, DENIED, UNCLEAR, NO_ANSWER, LAST4_MISMATCH, VERIFIER_DISAGREED or SUPERSEDED; each maps to one invoice transition or hold reason (PLAN.md §7.2, §7.3, §12.5).
- **Timeline and Audit Events**: the "Answered", status and decision entries shown in the callback stepper and the hash-chained audit log (PLAN.md §13.3, §14).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fraud sample with live voice, the vendor's phone rings within 15 seconds of the click that triggers the callback.
- **SC-002**: After the vendor says "no" and hangs up, the invoice shows HELD(DENIED_BY_VENDOR) on the dashboard within 3 seconds.
- **SC-003**: When the call is not answered, the invoice shows HELD(NO_ANSWER) within about 35 seconds of the callback request (25 s ring timeout plus provider reporting).
- **SC-004**: A replayed or duplicated webhook causes zero extra status transitions, audit events or agent starts.
- **SC-005**: Every voice webhook responds in under 1 second in tests and on the VM, and no request path invokes a language model.
- **SC-006**: The classifier passes all 11 rows of the PLAN.md §12.4 table; a tampered signature is rejected 100% of the time; an expired token never changes state.
- **SC-007**: The Heartland happy path (yes by keypad plus matching last four) ends RELEASED to the new account ending 4455 and the vendor master shows the verified change; the mismatch path ends HELD(LAST4_MISMATCH).
- **SC-008**: With `VOICE_MODE=simulated` and no credentials, every scenario in this spec can be demonstrated with the demo buttons, and `make test` passes with an empty `.env`.
- **SC-009**: With DEMO_MODE off, a simulated verification is never accepted for release.

## Dependencies & Scope

- **Owner**: Builder B (PLAN.md §0.1, §0.8), milestone B3 then the live phase after B4 (PLAN.md §18).
- **Depends on**: spec 002 for the public HTTPS URL and the `/twilio/*` edge route (live calls); spec 005 for the real pipeline handlers in PLAN.md §7.5 (code against stubs with the same signatures until it merges); spec 003 for `transition()`, the ledger and the audit log. The Twilio spike (B2, PLAN.md §18) proves dial, ring and answer timings before this spec's live phase.
- **Covers**: PLAN.md §12 in full, the voice interfaces in §7.5, the `verifications` table in §7.2, §16.4 and §16.5 provider notes, and the §17.1 rows for `test_classify.py`, `test_twilio_security.py` and `test_voice_flow.py`.
- **Out of scope**: the pipeline decision functions themselves (owner A, §12.5), the Verifier agent (§11), the dashboard stepper and demo buttons (specs 004, 007), the DevRev connector that creates change cases (spec 008), release eligibility and the ledger (§13), and provisioning the public URL (spec 002).

## Assumptions

- Spec Kit priorities P1, P2 and P3 here correspond to PLAN.md P0, P1 and P2 (constitution X). The last-four bank-change path is P2 because PLAN.md §4 places the Heartland case in P1, even though the prompt describes it in the core paragraph.
- Vendors in the seed data all have a phone on file; an invoice whose vendor cannot be resolved is held as UNKNOWN_VENDOR before any call (PLAN.md §10.1) and never reaches this feature.
- On stage, Builder B's phone is the vendor phone, the provider number is saved as a contact, and the confirmed path is demonstrated by pressing 1 (PLAN.md §12.5, §16.4, §19).
- `VOICE_MODE=simulated` is the default and remains so until the telephony account and `PUBLIC_BASE_URL` are READY in `make check-env` (PLAN.md §0.4); switching to `twilio` changes no logic other than placing a real call.
- Change-case calls (P3) reuse this feature unchanged; the change-case data arrives through spec 008's internal API.
- No secret values appear in this spec; credentials live in `.env` and are checked with `make check-env` (constitution VI).
