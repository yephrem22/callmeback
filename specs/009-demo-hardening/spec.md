# Feature Specification: Demo Hardening and Submission

**Feature Branch**: `009-demo-hardening`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Make the Call Me Back demo unbreakable and the submission complete.
P1: An end-to-end smoke test that runs all five samples against the deployed app, both with AI live and with AI off. A reset that restores the stage state. A pre-demo checklist.
P1: A README and a DevRev submission package.
P2: Fixes from rehearsal, only for issues that break the demo.
Details are in PLAN.md §17.2 to §17.4, §19 and §21."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command proves the deployed app still tells the whole story (Priority: P1)

After any deploy to the VM from 7 PM Saturday onward, either builder runs one end-to-end smoke command against the public URL (PLAN.md §17.2) and learns within minutes whether the five-sample demo story still holds. The command resets the demo, loads all five samples, answers the two callbacks the way the stage does (fraud = "no", Heartland = "yes" with last four 4455), approves the Prairie review, waits for every invoice to settle, and then checks the final states against PLAN.md §8.4, the audit chain seal, and the payment count. It is run twice per deploy, once with AI live and once with AI off, and both runs must pass.

**Why this priority**: The live call, the guardrail block, the simulate fallback, the reset button and the AI-off fallback are on PLAN.md §4's never-cut list, and the smoke is the only automated proof that a late-night fix did not break one of them. Without it, the 7:00 AM final deploy (PLAN.md §18) is a guess.

**Independent Test**: Run the smoke against the deployed VM with AI live, then again with AI off, and watch both exit with a pass report; then introduce a deliberate mismatch (for example, skip the Prairie approval) and watch it fail with a clear, per-sample reason instead of hanging.

**Acceptance Scenarios**:

1. **Given** the app is deployed and the caller holds the dashboard credentials, **When** the smoke runs with AI live, **Then** it resets, loads samples 01 to 05, simulates "no" on the Acme fraud callback, simulates "yes" plus 4455 on the Heartland callback, approves the Prairie review, polls each invoice until it is settled, and reports PASS only if 01 is RELEASED, 02 is HELD with reason DENIED_BY_VENDOR, 03 is RELEASED with the vendor master showing the new account ending 4455, 04 is RELEASED, 05 is HELD with reason UNKNOWN_VENDOR, the audit chain reports `chain_ok` true, and exactly three payments exist (for 01, 03 and 04).
2. **Given** the same deployment, **When** the smoke runs with AI off, **Then** the identical assertions pass, proving the rules alone carry the demo (PLAN.md §17.3 last item).
3. **Given** a sample never reaches its expected state, **When** the bounded wait expires, **Then** the smoke exits non-zero and names the sample, its observed state and the expected state; it never waits forever.
4. **Given** the smoke must simulate an answer or approve a review, **When** the invoice has not yet reached CALL_PENDING, CALLING or NEEDS_REVIEW, **Then** the smoke waits for that state before acting rather than acting early and receiving a conflict.
5. **Given** a deploy happens at or after 7 PM Saturday, **When** the deploy finishes, **Then** the smoke is run in both modes before the deploy is called done, and the result is noted in the rehearsal log.

---

### User Story 2 - The stage state can always be restored, and the pre-demo checklist is green (Priority: P1)

Before each rehearsal and before walking on stage, Builder A presses **Reset demo** and the dashboard returns to the exact starting state of the 3-minute pitch (PLAN.md §19.1): an empty case queue, the vendor master back to its seeded values (Heartland's bank update undone), a fresh audit chain, and the DevRev cases still present. Builder A then pre-runs the Heartland confirmation (press 1, then 4455) so it already appears in the audit log and vendor history, leaves Prairie unloaded, and walks the pre-demo checklist in PLAN.md §19.2 with Builder B until every item is checked. The pitch is rehearsed three times against the clock (PLAN.md §17.4), each segment's time and every glitch logged, and the manual live checks in PLAN.md §17.3 are completed with the real phone.

**Why this priority**: The reset button and the simulate fallback are never-cut (PLAN.md §4). A demo that cannot be returned to a known state, or a checklist item discovered broken at 8:50, ends the pitch; rehearsals are how the timing and the fallbacks become reflex.

**Independent Test**: From any mid-demo state (including a call still ringing), press Reset demo, confirm the queue is empty, the Heartland vendor shows the original bank, the audit log begins with a `demo_reset` genesis event and the DevRev cases tab still lists its cases; then pre-run Heartland and confirm RELEASED and the vendor master shows the new account ending 4455. Walk the §19.2 checklist and record each item as checked.

**Acceptance Scenarios**:

1. **Given** invoices, payments, calls and audit entries from a previous run, **When** Reset demo is confirmed, **Then** invoices, verifications, payments, traces and audit entries are wiped, vendors and invoice history are reseeded (undoing Heartland's bank change), the audit chain restarts with a `demo_reset` genesis event, the KPI strip restarts from zero, and DevRev change cases are kept (PLAN.md §7 `/api/demo/reset`).
2. **Given** the reset is requested with the explicit option to include change cases, **When** it completes, **Then** the DevRev cases are wiped too; by default they are not.
3. **Given** a fresh reset, **When** Builder A loads Heartland and simulates or performs "press 1, enter 4455", **Then** the invoice is RELEASED and the Vendors tab shows the new bank ending 4455, ready for the 2:15 segment of the pitch.
4. **Given** 8:00 to 8:45 AM Sunday, **When** the builders walk PLAN.md §19.2, **Then** every item is confirmed: B's phone charged, ringer on, Do Not Disturb off, Silence Unknown Callers off and the calling number saved as a contact; calling-service balance above $10 and a test call within the last 30 minutes; `/api/health` all green with inference latency shown; Reset demo done and Heartland pre-run RELEASED with Prairie unloaded; the DevRev cases tab shows at least one case; AI is LIVE and both builders know where the AI-off toggle is; the dashboard is logged in, light theme, 125% zoom, notifications off; `make check-env PHASE=demo` all READY; a phone hotspot is ready; and the backup plan (if the call does not ring within 15 s, open Demo controls and Simulate "no") is agreed.
5. **Given** the real phone, **When** the live checks in PLAN.md §17.3 are run, **Then** the fraud call rings within 15 s of the click, "No, we never changed banks" yields HELD on screen within 3 s of hang-up, Heartland press 1 plus 4455 yields RELEASED and the vendor master shows the account ending 4455, not answering yields HELD (NO_ANSWER) within about 35 s, the red-team button shows BLOCKED with no payment row, and with AI off the fraud sample still scores 160 and still calls.
6. **Given** three timed rehearsals, **When** each finishes, **Then** the log holds the time of every segment of the PLAN.md §19.1 table and every glitch, each glitch marked P0 or not.

---

### User Story 3 - The README and the DevRev package make the submission complete (Priority: P1)

A judge or organizer opening the repository at the `v1.0-submission` tag finds a README that follows the outline in PLAN.md §21 and a `devrev/` package that contains everything the DevRev Computer challenge asks for. Builder A writes the README; Builder B completes the DevRev package. At 7:00 AM the final deploy is smoked in both modes, `make check-env PHASE=demo` is all READY, the database is backed up, the repository is checked for leaked secrets, tagged `v1.0-submission` and pushed; the submission form is completed by 7:30 AM.

**Why this priority**: Submissions are due at 8:00 AM and 8:00 AM is a hard code freeze (PLAN.md §2); a missing README section or an incomplete DevRev package cannot be fixed afterwards. The submission is what the judges score; the demo is only three minutes of it.

**Independent Test**: Check out the tag on a clean machine, confirm the README has all ten outline headings with real content and a screenshot, confirm the `devrev/` folder holds every listed item, confirm the secret-pattern search returns nothing, and confirm the tag exists on the remote with a timestamp before 7:30 AM.

**Acceptance Scenarios**:

1. **Given** the repository at the tag, **When** the README is read, **Then** it contains, in order: (1) what it does, with one paragraph and a screenshot; (2) why it matters, with the brief's evidence and links; (3) design principles per PLAN.md §1; (4) the architecture diagram per PLAN.md §5 and the sponsor technology used (agents, plugins and validators; the cloud VM, inference, object storage and firewall; the FinTech controls; the DevRev skill and connector); (5) run locally, including that every integration starts in fake mode so no keys are needed; (6) deploy, summarizing PLAN.md §16; (7) tests, naming the unit suite and the smoke; (8) how it was built, pointing at `specs/`, `.specify/` and `docs/design/`; (9) limitations and roadmap (no PDF parsing, vendor-master edits need a callback to the old number, bank API integration, SSO); (10) credits (the DevRev starter adapted, the Akamai workshop kit patterns, the UI libraries and font, other libraries).
2. **Given** the `devrev/` folder, **When** it is inspected, **Then** it holds the skill folder; the connector source and configuration with no secrets; setup instructions; the tool contracts and access modes; the data boundary; `TESTS.md` with observed results including the second-user run and duplicate prevention; and known limitations (PLAN.md §21).
3. **Given** 7:00 AM Sunday, **When** the final deploy is complete, **Then** in order: the smoke passes with AI live and with AI off, `make check-env PHASE=demo` is all READY, the database backup is taken, the repository is searched for the account-SID pattern from PLAN.md §20 and the search returns nothing, the commit is tagged `v1.0-submission`, and the tag is pushed.
4. **Given** the organizers' form, **When** it is submitted by 7:30 AM, **Then** it carries the repo URL (private, organizers added if asked) at the tag, the challenges entered (Flex Best FinTech, AWS Best Use of Strands Agents SDK, Akamai Cloud AI, DevRev Computer, plus the corporate trophies if eligible), the live URL (credentials only on request), and the Phase 0 (A0) answers.

---

### User Story 4 - Rehearsal fixes are limited to what breaks the demo (Priority: P2)

From the 2:00 AM feature freeze onward, the builders change code only to fix a P0 glitch found in rehearsal: something that stops a segment of the 3-minute pitch, breaks the smoke, or breaks a never-cut item. Each fix is deployed, smoked in both modes and re-rehearsed. From 8:00 AM, no one touches the VM or the repository; the builders only rehearse and operate the dashboard.

**Why this priority**: PLAN.md §17.4 and §18 allow P0 fixes only after 2 AM precisely because a well-meant polish at 4 AM is the most likely way to break a working demo. This story is the discipline, not new work, so it ranks below the three deliverables.

**Independent Test**: Review the rehearsal log and the commit history between 2:00 and 8:00 AM: every commit maps to a logged P0 glitch and was followed by a passing two-mode smoke; no commit exists after 8:00 AM.

**Acceptance Scenarios**:

1. **Given** a glitch logged during a rehearsal after 2:00 AM, **When** the builders decide whether to fix it, **Then** it is fixed only if it is P0 (it breaks a pitch segment, the smoke or a never-cut item); otherwise it is logged and left.
2. **Given** a P0 fix after 2:00 AM, **When** it is deployed, **Then** the two-mode smoke is run and passes before the fix counts as done, and the affected pitch segment is rehearsed again.
3. **Given** 8:00 AM has passed, **When** anyone proposes a code or VM change, **Then** it is refused; only dashboard operation and rehearsal continue (PLAN.md §2, §17.4, §18).

---

### Edge Cases

- The smoke passes with AI live but fails with AI off (or the reverse): the deploy is not done; the failing mode is a P0 glitch because the AI-off fallback is never-cut.
- The smoke tries to simulate an answer while a real call is still active: simulate supersedes the active verification (PLAN.md §12.6), so the smoke is safe to run even if a rehearsal call is mid-flight, but it must never be run during the 8:00 to 9:00 AM window when the VM is frozen and the stage state is set.
- Reset is pressed while a call is ringing: everything is wiped, the stage state is restored, and the ringing call is simply abandoned; the builders re-run the Heartland pre-run afterwards.
- The DevRev cases tab is empty after a reset: the reset was run with the include-change-cases option, or the connector never created a case; Builder B re-creates one via the skill before 8:45 (PLAN.md §19.2).
- The call does not ring on stage within 15 s: Builder A uses Demo controls and Simulate "no" and says the venue network line; the rest of the pitch is identical (PLAN.md §19.2, §20).
- Inference is slow or rate-limited at demo time: switch AI to off; the decision never depends on the model (PLAN.md §20).
- Venue Wi-Fi drops: everything runs on the VM; the laptop moves to the phone hotspot (PLAN.md §20).
- The secret-pattern search finds a match before tagging: the secret is removed and rotated and the search is re-run before the tag is created; no tag is pushed with a secret in history.
- A rehearsal runs over 3:00: the segment times in the log show where; words are trimmed, not features added.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The end-to-end smoke MUST run against the deployed public URL with the dashboard credentials and perform, in order: reset; load all five samples; wait for and then simulate "no" for 02_acme_fraud; wait for and then simulate "yes" with last four 4455 for 03_heartland_bank_change; wait for and then approve the review for 04_prairie_review; poll each invoice until it is RELEASED, HELD or FAILED (PLAN.md §17.2).
- **FR-002**: The smoke MUST assert the final states of PLAN.md §8.4 (01 RELEASED; 02 HELD/DENIED_BY_VENDOR; 03 RELEASED with the vendor master updated to the account ending 4455; 04 RELEASED; 05 HELD/UNKNOWN_VENDOR), that the audit chain reports `chain_ok` true, and that exactly three payments exist (01, 03 and 04).
- **FR-003**: The smoke MUST be runnable with AI live and with AI off, switching the mode through the demo controls before the run, and MUST pass in both modes.
- **FR-004**: The smoke MUST finish within a bounded time and exit non-zero with a per-sample explanation on any failure; it MUST never print a credential.
- **FR-005**: The smoke MUST be run, in both modes, after every deploy from 7 PM Saturday onward, and the result recorded in the rehearsal log.
- **FR-006**: Reset demo MUST wipe invoices, verifications, payments, traces and audit entries; reseed vendors and invoice history (undoing Heartland's bank update); restart the audit chain with a `demo_reset` genesis event; and keep DevRev change cases unless explicitly asked to include them (PLAN.md §7).
- **FR-007**: The stage state MUST be defined as: reset done, Heartland pre-run to RELEASED with the vendor master showing the account ending 4455, Prairie unloaded, AI live, DevRev cases present (PLAN.md §19.1, §19.2).
- **FR-008**: The pre-demo checklist MUST contain exactly the items in PLAN.md §19.2 (phone settings and saved contact; calling-service balance above $10 and a test call within 30 minutes; health all green with inference latency; reset plus Heartland pre-run with Prairie unloaded; at least one DevRev case; AI live and the AI-off toggle known; dashboard logged in, light theme, 125% zoom, notifications off; `make check-env PHASE=demo` all READY; hotspot ready; the simulate backup plan) and MUST be walked between 8:00 and 8:45 AM.
- **FR-009**: The manual live checks in PLAN.md §17.3 MUST be completed with the real phone before the 2:00 AM feature freeze and any failure treated as P0.
- **FR-010**: Three full timed rehearsals of PLAN.md §19.1 MUST be run and logged with every segment's time and every glitch (PLAN.md §17.4); two more rehearsals run between 8:00 and 8:45 AM.
- **FR-011**: The README MUST follow the ten-section outline in PLAN.md §21 and credit adapted starter code (constitution principle XI).
- **FR-012**: The `devrev/` package MUST contain the skill folder, connector source and configuration without secrets, setup instructions, tool contracts and access modes, the data boundary, `TESTS.md` with observed results including the second user and duplicate prevention, and known limitations (PLAN.md §21).
- **FR-013**: The 7:00 AM sequence MUST be: final deploy; smoke in both modes; `make check-env PHASE=demo` all READY; database backup; secret-pattern search returning nothing; `git tag v1.0-submission`; push (PLAN.md §18, §20).
- **FR-014**: The submission form MUST be completed by 7:30 AM with the repo URL at the tag, the challenges entered, the live URL and the Phase 0 answers (PLAN.md §21).
- **FR-015**: From 2:00 AM, only P0 glitches MAY be fixed; every fix MUST be followed by a two-mode smoke. From 8:00 AM, no code, repository or VM change is permitted; only rehearsal and dashboard operation continue (PLAN.md §2, §17.4, §18).
- **FR-016**: No deliverable of this feature MAY contain a secret value; readiness is shown only through the masked `make check-env` output (constitution principle VI).

### Key Entities

- **Smoke run**: one execution against one base URL in one AI mode; records per-sample expected and observed state, `chain_ok`, payment count, duration and PASS/FAIL.
- **Stage state**: the known starting condition of the pitch (FR-007); produced by reset plus the Heartland pre-run.
- **Rehearsal log**: one entry per timed run with the time of each PLAN.md §19.1 segment, every glitch, its P0 classification and the fix or "left as is".
- **Pre-demo checklist**: the PLAN.md §19.2 items with a checked/unchecked state for the 8:00 to 8:45 AM walk.
- **Submission package**: the tagged repository (README per §21, `devrev/` per §21), the live URL, the challenge list and the form answers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the VM after the 7:00 AM final deploy, the smoke passes twice in a row with AI live and twice in a row with AI off, each run finishing in under five minutes.
- **SC-002**: Three timed rehearsals are logged before 8:00 AM, each under 3:00, with a time recorded for every segment of the PLAN.md §19.1 table.
- **SC-003**: `make check-env PHASE=demo` reports every row READY at 7:00 AM and again during the 8:00 to 8:45 AM checklist.
- **SC-004**: A database backup file dated Sunday morning exists on the VM before the tag is created.
- **SC-005**: The `v1.0-submission` tag is on the remote with a timestamp before 7:30 AM, and the submission form is completed by 7:30 AM.
- **SC-006**: Every item of the PLAN.md §19.2 checklist is checked by 8:45 AM, and all six PLAN.md §17.3 live checks passed with the real phone before 2:00 AM.
- **SC-007**: The README contains all ten outline sections with real content and a screenshot; the `devrev/` folder contains all seven required items; the secret-pattern search over the repository returns zero matches.
- **SC-008**: No commit, deploy or VM change exists with a timestamp after 8:00 AM Sunday; every commit between 2:00 and 8:00 AM maps to a logged P0 glitch.

## Dependencies & Scope

- **Owners**: Builders A and B (A: README, projector polish, rehearsal fixes, final smoke; B: DevRev package, phone setup, rehearsals, backups, per PLAN.md §18 A9, A10, B10).
- **Depends on**: everything; specs 001 to 008 must be merged and deployed. The smoke exercises 003's engine, 005's pipeline and API, 006's callbacks and simulate path, 007's dashboard controls and 002's deployment; the DevRev checklist item depends on 008.
- **Out of scope**: any new feature after 2:00 AM, including the P2 sandbox call from a change case named in PLAN.md §18 B10 unless it is already working; any UI change not needed to fix a P0 glitch; any change to PLAN.md §7 contracts.
- **PLAN.md sections covered**: §2 (freeze), §4 (never-cut list), §17.2 to §17.4, §18 (overnight and Sunday timeline), §19, §20 and §21.

## Assumptions

- The dashboard credentials and the AI-mode, reset and simulate controls from PLAN.md §7 exist as built by specs 005 and 007; this feature adds no endpoints.
- "Settled" for the smoke means RELEASED, HELD or FAILED; HELD is the expected end state for samples 02 and 05 even though the state machine allows a later retry.
- A five-minute ceiling per smoke run is generous for five samples with per-agent timeouts in place; it exists so a hang is reported as a failure rather than waited on.
- Dashboard operation (reset, loading samples, simulate) between 8:00 and 9:00 AM is not a VM or code change and is permitted by the freeze; deploys, SSH sessions and commits are not.
- The organizers' form fields beyond those in PLAN.md §21 are answered from the Phase 0 (A0) decisions recorded in `docs/decisions.md`.
- The rehearsal log is a plain text or markdown note kept by the builders; its location is decided in planning and it is not a product feature.
