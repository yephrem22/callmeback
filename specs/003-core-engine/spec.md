# Feature Specification: Core Engine (intake, policy, state machine, ledger, audit)

**Feature Branch**: `003-core-engine`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "The deterministic core of Call Me Back, an accounts-payable safeguard against fake bank-change invoices. With no AI and no phone involved, it must:
- ingest invoice emails (five sample emails plus .eml upload) and extract the invoice fields from the text;
- resolve which vendor the email claims to be from, including lookalike domains;
- score red flags with disclosed points, and route each invoice to auto-release, human review, a phone callback or a manual hold;
- keep a strict payment state machine;
- keep a ledger that releases only eligible payments, and only to the bank account in the vendor master;
- record vendor-master bank changes with their history;
- keep a tamper-evident, hash-chained audit log.
P1: The five samples produce exactly the expected results in PLAN.md §8.4.
P1: Release is impossible unless policy allows it.
P2: The vendor master updates after a confirmed bank change.
Everything is in PLAN.md §7, §8, §9, §10 and §13."

This feature is the code that "holds the keys" (PLAN.md §1, principle 1). Everything it decides is deterministic, reproducible with the AI switched off and no phone connected, and leaves evidence. The shared contracts in PLAN.md §7.1 to §7.4 (environment variables, database schema, status machine, core models) are adopted as written, not redesigned; they are **frozen** once this feature's first phase (the skeleton and contracts, milestone A1) is green. Later specs (005 agents, 006 voice, 007 UI) build on them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Five samples are scored and routed exactly as expected (Priority: P1)

An AP clerk loads any of the five demo invoice emails (PLAN.md §8.3). Without any AI or phone, the system reads the email, pulls out the invoice number, amount, due date, bank name, routing and account numbers, works out which vendor the email claims to come from (including a domain that imitates a real vendor's), scores each red flag with disclosed points, and routes the invoice to automatic release, human review, a phone callback or a manual hold. The result matches PLAN.md §8.4 to the flag and the point.

**Why this priority**: This is the demo spine (PLAN.md §4 P0). Every later feature (calls, agents, dashboard) consumes these results; if they are wrong, nothing downstream can be right.

**Independent Test**: Load each sample with AI off and compare the flags, points, tier and action with the §8.4 table. No other feature is needed.

**Acceptance Scenarios**:

1. **Given** AI is off and the vendor master and invoice history from PLAN.md §8.1 and §8.2 are seeded, **When** each sample is ingested and scored, **Then** the result is exactly:

| Sample | Flags (points) | Points | Tier | Action |
|---|---|---|---|---|
| 01_acme_normal | none | 0 | GREEN | AUTO_RELEASE |
| 02_acme_fraud | LOOKALIKE_DOMAIN 40, BANK_CHANGED 50, REPLY_TO_MISMATCH 20, AMOUNT_3X 25 (4.06×), URGENCY 10, AVOID_VERIFICATION 15, AI_DIRECTED_TEXT 0, PHONE_IN_EMAIL 0 | 160 | RED | CALLBACK |
| 03_heartland_bank_change | BANK_CHANGED 50 | 50 | RED | CALLBACK |
| 04_prairie_review | AMOUNT_2X 15 (2.10×), URGENCY 10 | 25 | YELLOW | REVIEW |
| 05_unknown_vendor | UNKNOWN_VENDOR 30, INVALID_ROUTING 30 | 60 | RED | HOLD_MANUAL |

2. **Given** sample 02, **When** the sender is resolved, **Then** the vendor is Acme with sender status LOOKALIKE, and the lookalike explanation reads like "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')" (PLAN.md §10.1).
3. **Given** sample 02, **When** the body is scanned, **Then** the phone number "(816) 555-0142" is found and the ten-digit account number "7730019942" is not treated as a phone number (PLAN.md §9.2).
4. **Given** samples 01 and 03, **When** the phrase lists in PLAN.md §10.3 are applied to subject and body, **Then** nothing matches.
5. **Given** any sample, **When** the fields are extracted from the text, **Then** routing, account, amount and invoice number equal the values written in the email (PLAN.md §9.2), and every extracted field records where it came from (PLAN.md §7.4 FieldValue).
6. **Given** the routing numbers in the five samples, **When** the ABA checksum is applied, **Then** all pass except 071000014 (PLAN.md §8.4, §17.1).
7. **Given** a scored invoice, **When** its status is read, **Then** it has moved RECEIVED → EXTRACTED → SCORED and then to AUTO_APPROVED, NEEDS_REVIEW, CALL_PENDING or HELD (UNKNOWN_VENDOR) according to its action (PLAN.md §7.3), and audit events `invoice_received`, `extraction_done`, `vendor_resolved`, `risk_scored` and `status_changed` exist for it.

---

### User Story 2 - Release is impossible unless policy allows it (Priority: P1)

A payment leaves the building only when the invoice is in an eligible state and the eligibility rules in PLAN.md §13.1 are satisfied, and the money always goes to the bank account in the vendor master, never to one quoted in an email. A compromised agent, a retried webhook or a double click cannot produce a payment the policy did not approve.

**Why this priority**: "The AI can always say no; only verified code paths can say yes" (PLAN.md §1, constitution II). This is the property the whole product exists to guarantee and it is P0 in PLAN.md §4.

**Independent Test**: Drive invoices into each status by hand, attempt a release from each, and check that exactly the §13.1 rows release and everything else is refused with a human-readable reason and a `release_blocked` audit event.

**Acceptance Scenarios**:

1. **Given** an invoice in AUTO_APPROVED with tier GREEN and action AUTO_RELEASE, **When** release is requested, **Then** one payment is recorded for the invoice amount to the vendor master's routing and account, the effective date is the next business day, the status becomes RELEASED and a `payment_released` audit event is written.
2. **Given** an invoice in HELD (any reason), **When** release is requested, **Then** it is refused with a reason such as "invoice is HELD (vendor denied the change ...)", no payment exists, and a `release_blocked` audit event is written.
3. **Given** an invoice in any status other than AUTO_APPROVED, REVIEW_APPROVED or CONFIRMED, **When** release is requested, **Then** it is refused (PLAN.md §13.1 "anything else: never").
4. **Given** an invoice in CONFIRMED whose risk says the bank changed, **When** the latest verification is CONFIRMED but the last-four challenge did not pass, **Then** release is refused.
5. **Given** an invoice in CONFIRMED whose verification came from a simulated call, **When** demo mode is off, **Then** release is refused; when demo mode is on, it is allowed.
6. **Given** an invoice in NEEDS_REVIEW, **When** a reviewer approves, **Then** it becomes REVIEW_APPROVED and is releasable only because its action was REVIEW and the recorded decision is "approve"; a rejection moves it to HELD (REVIEW_REJECTED).
7. **Given** a releasable invoice, **When** release is requested twice, **Then** exactly one payment exists.
8. **Given** any invoice, **When** a status change that PLAN.md §7.3 does not allow is attempted, **Then** it is rejected as illegal; repeating a change to the status the invoice already has is a no-op that reports "nothing changed"; HELD without a hold reason, or with a reason not allowed for that from-state, is rejected.
9. **Given** an invoice in HELD, **When** a retry is requested, **Then** it returns to CALL_PENDING only if the hold reason is UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED or VERIFIER_DISAGREED.
10. **Given** an invoice in a releasable state, **When** an agent asks to hold it, **Then** it becomes HELD (AGENT_HOLD); asking again records `hold_confirmed` and changes nothing else.

---

### User Story 3 - The vendor master updates after a confirmed bank change (Priority: P2)

Heartland genuinely moved banks (sample 03). After the vendor confirms the change on a callback to the number on file and passes the last-four challenge, the vendor master is updated to the new bank, the old details are kept in a history, and the payment goes to the new account. Until that confirmation, the vendor master and every payment destination are unchanged.

**Why this priority**: PLAN.md §4 lists the Heartland path as P1 (the next step after the demo spine). It proves that the system can say yes to a legitimate change, not only no to fraud.

**Independent Test**: Seed the vendors, score sample 03, record a CONFIRMED verification with the last four matching 4455, apply the bank change, release, and inspect the vendor, its history and the payment.

**Acceptance Scenarios**:

1. **Given** sample 03 is CONFIRMED with a passing last-four check, **When** the bank change is applied, **Then** Heartland's vendor record shows Gateway National Bank, routing 044000105, account ending 4455; one history row records River City Bank / 102030402 / ••••3377 → Gateway National Bank / 044000105 / ••••4455 with the invoice and verification that justified it; and a `vendor_bank_updated` audit event exists.
2. **Given** the bank change has been applied, **When** the invoice is released, **Then** the payment destination is the updated vendor master (••••4455), as required by PLAN.md §13.1 step 2.
3. **Given** sample 02 (the fraud), **When** the vendor denies the change and the invoice is HELD, **Then** Acme's vendor record is unchanged and its history is empty.
4. **Given** a demo reset, **When** vendors are reseeded, **Then** Heartland is back on River City Bank and the history is empty (PLAN.md §7.6 reset semantics).

---

### User Story 4 - Every decision leaves tamper-evident evidence (Priority: P2)

A judge or auditor can read the chronological record of everything that happened to an invoice and verify that nobody edited it after the fact: each entry is chained to the one before, and changing a single entry breaks the chain at a known position.

**Why this priority**: PLAN.md §4 lists the hash-chained audit log as P1. Plain audit events are required by every story above (constitution VII); the chain is the proof that they are trustworthy.

**Independent Test**: Append several entries, verify the chain, alter one stored entry directly, and verify again.

**Acceptance Scenarios**:

1. **Given** five entries appended in sequence, **When** the chain is verified, **Then** it is reported intact.
2. **Given** an intact chain, **When** one entry's data is altered in storage, **Then** verification reports a break and names that entry's sequence number as the first broken one.
3. **Given** two writers appending at the same moment, **When** both finish, **Then** sequence numbers are consecutive with no gap or duplicate and the chain still verifies.
4. **Given** any audit entry, **When** it is read, **Then** account and phone numbers in its data show only their last four digits (PLAN.md §6 masking) and its actor and event names come from PLAN.md §13.3.

---

### User Story 5 - Upload my own invoice email (Priority: P3)

An AP clerk uploads a real `.eml` file instead of picking a sample. The same extraction, resolution, scoring and routing run on it, so the demo is visibly not hard-wired to the five samples.

**Why this priority**: The demo spine in PLAN.md §4 runs on the samples; upload proves generality and is worth having only once the samples are green.

**Independent Test**: Upload a hand-written `.eml` that mentions a seeded vendor and verify it is parsed and scored by the same rules.

**Acceptance Scenarios**:

1. **Given** a well-formed `.eml` under 1 MB with a plain-text body, **When** it is uploaded, **Then** it is stored with a content fingerprint, parsed per PLAN.md §9.1, and scored exactly as a sample would be.
2. **Given** an upload over 1 MB or one that cannot be parsed, **When** it is submitted, **Then** it is rejected and nothing is scored.
3. **Given** an email whose body is HTML only, **When** it is parsed, **Then** tags are stripped and the text is extracted; attachments are ignored.

---

### Edge Cases

- Two different routing or account numbers in one email: the first is kept and a 0-point EXTRACTION_MISMATCH flag is added (PLAN.md §9.2). Points, tier and action do not change.
- Routing number fails the checksum: it is still extracted; INVALID_ROUTING scores it (PLAN.md §9.2, §10.2).
- Known vendor, no bank details in the email: NO_BANK_DETAILS (0 points) and the payment goes to the account on file; a missing value never counts as "changed" (PLAN.md §10.2).
- A phrase split across a line break (sample 02's "release the / payment immediately") still matches, because whitespace is collapsed before matching (PLAN.md §10.3). "Today" inside "today's" does not match, because phrases must stand alone.
- "Invoice November ..." is not read as an invoice number (PLAN.md §9.2).
- Subdomain of a vendor domain (mail.acme-supply.com) is KNOWN, not LOOKALIKE; gmail.com is neither (PLAN.md §17.1 vectors).
- Vendor with fewer than three paid invoices: no amount flags.
- LOOKALIKE and UNRECOGNIZED_SENDER never fire together; UNKNOWN_VENDOR always routes to HOLD_MANUAL even if the tier would otherwise call for a callback.
- Statuses RELEASED and FAILED are terminal; only a demo reset clears them.
- With AI off, extraction is text-only, the extraction records that no model contributed (PLAN.md §7.4 `llm_status`), and every result above still holds. Model output can never change a scored input (PLAN.md §9.3, §9.4), so scoring never waits on a model.
- Release attempted while the vendor master is mid-update: the release and its audit event commit together or not at all (PLAN.md §13.1 single transaction).

## Requirements *(mandatory)*

### Functional Requirements

**Contracts**

- **FR-001**: The system MUST adopt the environment variables, database schema, status machine and core models exactly as written in PLAN.md §7.1, §7.2, §7.3 and §7.4, and MUST declare them frozen at the end of this feature's first phase (milestone A1). Any later change requires both builders' agreement (constitution I).
- **FR-002**: Money MUST be stored as integer cents, time as UTC ISO-8601, identifiers with the prefixes in PLAN.md §6, and account and phone numbers MUST be masked to their last four digits in every output other than the database.

**Intake**

- **FR-003**: The system MUST ingest an invoice email either from the five samples in PLAN.md §8.3 (copied verbatim, with a manifest of name, title and description) or from an uploaded `.eml` of at most 1 MB, rejecting oversized or unparseable input.
- **FR-004**: The system MUST parse sender name, address and domain, reply-to address and domain, subject, date and body per PLAN.md §9.1, preferring plain text, stripping HTML when that is all there is, ignoring attachments, and keeping a content fingerprint of the raw bytes.
- **FR-005**: The system MUST extract routing number, account number, amount, invoice number, bank name and due date from the text using the label-anchored patterns in PLAN.md §9.2 exactly, keeping the first match, and MUST find US phone numbers only when separators or parentheses are present.
- **FR-006**: The system MUST merge text-derived and model-derived values per PLAN.md §9.3 so that text always wins and any digits not present verbatim in the body are discarded; with AI off, the text-derived values stand alone.

**Vendor resolution, scoring and routing**

- **FR-007**: The system MUST resolve the vendor in the order exact domain, lookalike domain, fuzzy name, none, yielding sender status KNOWN, LOOKALIKE, UNRECOGNIZED or NO_VENDOR per PLAN.md §10.1, using the skeleton and distance rules given there and producing a human-readable lookalike explanation.
- **FR-008**: The system MUST evaluate exactly the flags, points and firing conditions in PLAN.md §10.2, each phrase-based flag firing at most once and listing every matched phrase as evidence, using the phrase lists and normalisation in PLAN.md §10.3.
- **FR-009**: The system MUST compute the uncapped point total, the tier (GREEN below 20, YELLOW from 20 to below 50, RED from 50) and the action by the first-match routing order in PLAN.md §10.2, and record the result in the shape of PLAN.md §7.4 RiskResult, including the policy version.
- **FR-010**: Scoring MUST read only the invoice fields and the vendor master and history; it MUST NOT depend on any model output or any network call, and MUST produce identical results on every run.
- **FR-011**: The vendor master and invoice history in PLAN.md §8.1 and §8.2 MUST be seeded (medians 12,020.00, 3,995.00 and 2,499.00; paid dates a month apart from April to September 2026) and MUST be restorable by a demo reset.

**State machine**

- **FR-012**: Status changes MUST be atomic compare-and-set transitions that permit only the from/to pairs in PLAN.md §7.3, require a hold reason allowed for the from-state whenever the target is HELD, treat a repeat of the current status as a no-op, reject anything else as illegal, and write a `status_changed` audit event in the same transaction.
- **FR-013**: Retry from HELD to CALL_PENDING MUST be permitted only for UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED and VERIFIER_DISAGREED; RELEASED and FAILED MUST be terminal.

**Ledger**

- **FR-014**: A single eligibility check MUST implement the PLAN.md §13.1 matrix (AUTO_APPROVED with GREEN and AUTO_RELEASE; REVIEW_APPROVED with action REVIEW and an "approve" decision; CONFIRMED with a CONFIRMED latest verification from a real call, or a simulated one in demo mode, plus a passing last-four check when the bank changed; nothing else), re-reading current state each time and returning a human-readable reason when blocked. The same check MUST be the one later features (the agent guardrail) call.
- **FR-015**: Release MUST, in one transaction, re-check eligibility, refuse with a `release_blocked` audit event and an error when not eligible, otherwise record exactly one payment per invoice whose destination is the vendor master at release time (never the email), set the effective date to the next business day, move the invoice to RELEASED and write `payment_released`.
- **FR-016**: Hold MUST be idempotent: from a releasable state it moves to HELD (AGENT_HOLD); from HELD it records `hold_confirmed`.
- **FR-017**: Human review MUST record approve or reject with a note, moving NEEDS_REVIEW to REVIEW_APPROVED or HELD (REVIEW_REJECTED) and writing `review_decision`.

**Vendor master change control**

- **FR-018**: After a CONFIRMED verification on an invoice whose bank details changed, the system MUST write a history row (old bank, routing, account → new) tied to the invoice and verification, update the vendor master, and write `vendor_bank_updated`. The vendor master MUST change through no other path.

**Audit**

- **FR-019**: Every audit entry MUST carry a consecutive sequence number, timestamp, subject, actor and event from PLAN.md §13.3, masked canonical data, the previous entry's hash and its own hash computed as in PLAN.md §13.2; appends MUST be serialised so concurrent writers cannot read the same last entry.
- **FR-020**: The system MUST be able to verify the whole chain in sequence order and report whether it is intact and, if not, the first broken sequence number.
- **FR-021**: Every decision in this feature (receipt, extraction, resolution, scoring, status change, review, hold, release, vendor update) MUST write an audit event (constitution VII).

**Fixtures and testing**

- **FR-022**: The system MUST provide a fixtures export that runs the engine on each sample with AI off and simulated verification outcomes, drives each to its PLAN.md §8.4 final state, and writes the per-step results in the PLAN.md §7.6 InvoiceDetail shape for the UI session to consume.
- **FR-023**: The deterministic parts (checks, phrases, extraction, policy vectors, state machine, ledger, audit) MUST have unit tests built from the PLAN.md §8.4, §10 and §17.1 vectors, and the whole suite MUST pass with AI off, no credentials and no network.

### Key Entities *(include if feature involves data)*

- **Vendor**: a trusted supplier in the vendor master: name, the domains it legitimately writes from, the phone number on file (the only number ever called), and its current bank name, routing and account. Source of truth for every payment destination.
- **Vendor bank history**: one row per confirmed change to a vendor's bank details: old and new bank, routing and account, the invoice and verification that justified it, and when it happened.
- **Invoice history**: past paid invoices per vendor (number, amount, date), used to compute the median against which a new amount is compared.
- **Invoice**: one ingested email and everything decided about it: source (sample or upload), fingerprint, sender and reply-to details, subject and body, the extraction, the resolved vendor, the risk result, any review decision, current status and hold reason, and a version counter.
- **Extraction**: the invoice fields pulled from the email, each with a value and its provenance (text, model, both, header or none) and whether the text and model disagreed.
- **Risk result and flag**: the scored outcome: a list of flags (code, points, title, specific detail, evidence), the point total, tier, action, sender status, whether the bank changed, the proposed bank details, the amount and the vendor's median, and the policy version.
- **Verification**: the outcome of an out-of-band check on an invoice or change case: the number called, source (real or simulated), step, answers, last-four result and final label. Created by later features; read here to decide eligibility.
- **Payment**: a released payment: invoice, amount, destination copied from the vendor master, method, effective date, when and by whom it was released. At most one per invoice.
- **Audit entry**: a sequenced, hash-chained record of one event: time, subject, actor, event, masked data, previous hash and own hash.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With AI off and no phone, all five samples produce exactly the PLAN.md §8.4 flags, points, tier and action, on every run, in under one second each.
- **SC-002**: Every test vector in PLAN.md §17.1 for checksums, lookalike domains, phone finding, phrases and field extraction passes; samples 01 and 03 match zero phrases.
- **SC-003**: No release can occur from a non-eligible state: across every row of the PLAN.md §13.1 matrix and every other status, only the eligible combinations produce a payment, and every refusal carries a human-readable reason and a `release_blocked` audit event.
- **SC-004**: Two release requests for the same invoice produce exactly one payment; a release from HELD produces zero payments.
- **SC-005**: Every recorded payment's destination equals the vendor master at release time; no payment ever carries bank details that exist only in an email.
- **SC-006**: After the confirmed Heartland change, the vendor master reads Gateway National Bank ••••4455, exactly one history row records the old and new details, and the released payment goes to ••••4455; after the denied Acme change, Acme's record and history are untouched.
- **SC-007**: A tampered audit row is detected: altering any one entry makes verification fail and name that entry's sequence number; an unaltered chain of any length verifies intact.
- **SC-008**: Every illegal status transition is rejected, every repeated transition is a no-op, and every legal transition appears as a `status_changed` audit event; 100% of the from/to pairs in PLAN.md §7.3 are covered by tests.
- **SC-009**: The complete test suite passes with AI off, zero credentials configured and no network access.
- **SC-010**: The fixtures export produces, for every demo scenario step, output that validates against the PLAN.md §7.6 InvoiceDetail shape, so the UI session can start without a running backend.
- **SC-011**: The PLAN.md §7.1 to §7.4 contracts are unchanged between the end of phase 1 and the end of the feature.

## Dependencies & Scope

- **Owner**: Builder A.
- **Depends on**: nothing. Phase 1 is the skeleton and the contracts (milestone A1); it is pushed as soon as it is green and announced as "contracts frozen" so the other sessions can build against it.
- **Feeds**: the fixtures exporter (FR-022) feeds the UI session (spec 007); the eligibility check (FR-014) is what the agent guardrail (spec 005) calls; the state machine and verification records are what the voice routes (spec 006) drive.
- **PLAN.md sections covered**: §7.1 to §7.4 (contracts), §8 (demo data and test vectors), §9 (intake), §10 (policy engine), §13.1 to §13.3 (ledger and audit), and the §17.1 tests for these.
- **Out of scope** (other specs): the AI agents and their guardrail plugin and traces (spec 005); phone calls, call classification, Twilio security and the verification call flow (spec 006); the dashboard and its fixtures consumption (spec 007); HTTP routes beyond what the engine itself needs to ingest, review, hold, release and reset; Object Storage, the internal API and the DevRev connector (Builder B). Where this spec mentions a verification, it means a record created by spec 006 or by the fixtures exporter's simulated outcomes.

## Assumptions

- PLAN.md is the source of truth; where this spec is terser than PLAN.md, PLAN.md's text governs, and where they disagree PLAN.md wins and this spec is corrected.
- The five sample emails are copied character for character from PLAN.md §8.3 (with the two extra MIME headers it asks for); any difference would invalidate the §8.4 vectors.
- The policy version is "2026-10-10.1" per PLAN.md §7.4; changing points or phrases later means bumping it.
- "AI off" is the default mode for every test and for the fixtures export; nothing in this feature calls a model, a phone provider or the network.
- Demo mode is on in tests that exercise simulated verifications, and off in the test that proves a simulated verification is refused otherwise.
- The next business day for a payment's effective date skips Saturdays and Sundays only; holidays are not modelled.
- Demo data are fictional; no email is ever sent to any domain in the samples.
- Nothing in this repository predates the hackathon kickoff (constitution XI); libraries are allowed.
