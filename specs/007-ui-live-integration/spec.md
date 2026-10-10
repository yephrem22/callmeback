# Feature Specification: UI Live Integration

**Feature Branch**: `007-ui-live-integration`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Connect the approved Call Me Back prototype to the live API, so every pipeline step shows up within a second, and make it ready for the stage.
P1: Live polling of the queue and the open case. The decision, risk, destination, callback, payment and audit panels show real data. Demo controls (reset, simulate answer, AI on or off) and a health header.
P1: The full 3-minute demo story works end to end in light mode on a 1280×720 projector.
P2: Dark-mode polish, the trace sheet, the red-team dialog, and the DevRev cases, vendors and payments tabs.
Details are in PLAN.md §14 and §19."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The case comes alive on the real API (Priority: P1)

An AP specialist (PLAN.md §14.1) loads a sample or picks an invoice from the queue and watches the case fill in from the live backend as the pipeline runs: the decision stamp and its one-sentence reason, the risk flags, the destination card, the callback stepper and transcript, the payment card and the audit list all update on their own, with no refresh. The presenter can reset the demo, switch the AI live or off, and simulate a vendor answer from the Demo controls tab, and the header shows whether the database, inference, telephony and storage are healthy. This is the PLAN.md §18 A7 milestone ("dashboard runs on the live API") and PLAN.md P0.

**Why this priority**: Without live data the approved prototype from spec 004 is a picture. Every other story, the 7 PM checkpoint and the pitch depend on the queue and the open case reflecting the backend within a second.

**Independent Test**: Start the API in demo mode with AI off, open the dashboard in live mode, load "Acme: urgent bank change", and confirm each pipeline state (received, scored, calling, held) appears in the case within one second of the backend reaching it; then use Simulate "no", Reset demo and the AI toggle and confirm the panels and header reflect each action.

**Acceptance Scenarios**:

1. **Given** the dashboard is open in live mode with an empty queue, **When** the presenter loads a sample, **Then** the new invoice appears in the queue, is selected automatically, and its panels show the backend's data within one second of each status change.
2. **Given** an open case that has not reached RELEASED, HELD or FAILED, **When** the backend changes its status, **Then** the case refreshes within one second; **and** once the case is terminal the refresh slows to every five seconds while the queue keeps refreshing every two seconds.
3. **Given** a case in each demo state (PLAN.md §19.1), **When** the decision panel renders, **Then** the stamp shows PAID, HELD, REVIEW or CALLING and exactly one of the five sentences in PLAN.md §14.9 ("Paid. ACH effective Oct 12.", "Waiting for the vendor to answer.", "Held. The vendor said no on the 10:42 call.", "Needs review: the amount is 2.1 times usual.", "Held. No vendor record, so there's no trusted number to call."), with the date, time and ratio taken from the live data.
4. **Given** `actions.can_review` is true, **When** the specialist clicks "Approve payment", **Then** the review request is sent, the toast "Payment approved" appears, and the case moves to its released or held state through polling, not through a local guess.
5. **Given** demo mode is on, **When** the presenter clicks "Reset demo" and confirms, **Then** the queue empties, the case shows "Load a sample invoice to start.", the toast "Demo reset" appears, and the DevRev cases tab still lists its cases.
6. **Given** the presenter switches AI off, **When** the header re-polls, **Then** it reads "AI: off (rules only)" and new analyst notes show the "Rules fallback" chip.

---

### User Story 2 - The 3-minute story runs end to end on the projector (Priority: P1)

The presenter walks through the PLAN.md §19.1 pitch in order (empty dashboard, Acme normal → PAID, Acme fraud → RED with flags, live call → HELD, "Try to make the AI pay" → blocked, Audit and Vendors tabs, DevRev cases tab, header with "Running on" and the deploy label) in the light theme at 125% zoom on a 1280×720 projector, and every step is legible from five metres without explanation. PLAN.md P0.

**Why this priority**: This is the deliverable judged on stage. A live case that fails one step of the story, or that cannot be read from the back of the room, loses the demo.

**Independent Test**: Run the pre-demo checklist in PLAN.md §19.2, then perform the §19.1 script against the live API with a simulated "no" answer; the run must complete without touching anything outside the dashboard and with no console errors.

**Acceptance Scenarios**:

1. **Given** a reset backend with Heartland pre-run per PLAN.md §19.1, **When** the presenter performs every row of the §19.1 script, **Then** each screen named in the "Screen" column appears with the data the "Words" column describes, in order, in light mode at 1280×720 and 125% zoom.
2. **Given** the live call does not ring within 15 seconds, **When** the presenter opens Demo controls and clicks Simulate "no", **Then** the callback stepper, transcript (with a SIMULATED badge) and the HELD stamp appear exactly as they would for a real call (PLAN.md §19.2 backup plan).
3. **Given** the header is visible, **When** the final §19.1 row is reached, **Then** it shows "Running on" followed by the deploy label, the inference latency, four health dots with tooltips, the theme toggle and the AI state.
4. **Given** the Audit log tab is open for the held invoice, **When** the chain check returns intact, **Then** the tab shows the "Chain verified" header above the entries, each with its short hash, and an export link (P1 per PLAN.md §14.9).

---

### User Story 3 - The secondary surfaces are polished (Priority: P2)

A controller or an AWS judge opens the agent trace sheet to see each agent and tool span, runs the red-team action and reads which layer blocked it, browses the Payments tab (KPI strip and ledger), the Vendors tab (vendor master and bank-change history), and the DevRev cases tab, and switches to dark mode without losing contrast or meaning. This is the PLAN.md §18 A8 milestone and PLAN.md P1.

**Why this priority**: These surfaces prove the "AI explains; code holds the keys" claim and the vendor-master change control, but the pitch survives without their polish, so they follow the live case and the story.

**Independent Test**: On a held fraud invoice, click "Try to make the AI pay" and confirm the dialog names the blocking layer and the trace sheet opens with the guard block in the held color; then open each tab in both themes and confirm the live data and contrast.

**Acceptance Scenarios**:

1. **Given** `actions.can_redteam` is true, **When** the presenter clicks "Try to make the AI pay" (held-color outline), **Then** a dialog states which layer blocked the attempt (plugin, ledger or agent refused) and why, the trace sheet opens automatically, and no payment appears.
2. **Given** the Payments tab is open, **When** payments have been released and held since the last reset, **Then** the KPI strip shows money released, money held, invoices, calls placed and median decision time, and the ledger lists each released payment with a masked destination and ACH effective date.
3. **Given** the Vendors tab is open after the Heartland confirmation, **When** the vendor row renders, **Then** the bank-change history shows before and after, marked as verified by callback.
4. **Given** dark mode is selected, **When** any panel renders, **Then** text contrast is at least 4.5:1, status still carries a word and an icon, and the theme choice persists across reloads.

---

### User Story 4 - ACH batch download (Priority: P3)

A controller downloads the ACH batch for released payments from the Payments tab. PLAN.md §14.9 marks this P2 (spec P3); it depends on the NACHA export in PLAN.md §4 P2.

**Why this priority**: Nice to show finance judges, never at the expense of P1 or P2 (PLAN.md §18 A11).

**Independent Test**: With at least one released payment, click the download control on the Payments tab and receive a file.

**Acceptance Scenarios**:

1. **Given** released payments exist and the export exists on the backend, **When** the controller clicks the download, **Then** a batch file is delivered; **and** when the export is not built, the control is absent rather than broken.

---

### Edge Cases

- Health cannot be fetched: the header dots show an error state with a tooltip saying what failed; the queue and case keep polling independently.
- The chain check returns not intact: the Audit log header must not say "Chain verified"; it names the sequence where the chain broke (`broken_at`).
- A demo action returns 409 (simulate when not allowed, retry when not retryable, review when not in review, red team when payable): the UI shows an error that says what happened and what to do next (PLAN.md §14.6 copy rules); the buttons were already hidden by `actions`, so this only occurs on a stale view, and the next poll corrects it.
- `destination.requested` is null (no bank details in the email): the destination card shows only the account on file, with no "changed" marking.
- `vendor.history` is empty and `vendor` is unresolved (UNKNOWN_VENDOR): the amount-vs-history view and the median are omitted, and the decision sentence is the "No vendor record" one.
- `verification.source` is "simulated": the callback panel carries a SIMULATED badge; a real call never shows it.
- `ai_fallback` is true or `extracted.llm_status` is not "ok": the analyst note shows the "Rules fallback" chip and the field chips read "text"; nothing claims AI agreement.
- Reset while a case is selected: the selection is cleared and the case area shows the empty-queue copy; no stale invoice remains selected.
- Polling while the backend is briefly unreachable: the last good data stays on screen, no toast fires, and polling resumes without a page reload.
- `prefers-reduced-motion` is set: the stamp does not animate; everything else is unchanged.
- Fixtures mode with no backend: the scenario player and all panels still work from `web/src/fixtures/`, and no request is made to `/api`.

## Requirements *(mandatory)*

### Functional Requirements

**Polling and selection (PLAN.md §14.9)**

- **FR-001**: In live mode the dashboard MUST refresh the invoice list every 2 seconds, the open case every 1 second until its status is RELEASED, HELD or FAILED and every 5 seconds after that, and health every 15 seconds.
- **FR-002**: Loading a sample MUST select the newly created invoice.
- **FR-003**: The dashboard MUST never advance a status locally; every state shown MUST come from the API.

**The case (PLAN.md §14.9, §7.6)**

- **FR-004**: The decision panel MUST show the stamp (PAID, HELD, REVIEW or CALLING) plus exactly one of the five sentences listed in PLAN.md §14.9, filled from live data.
- **FR-005**: The risk panel MUST list each flag as `+points Title` with its detail and evidence; 0-point flags appear as notes with an info icon.
- **FR-006**: The extracted-fields table MUST show one chip per field: "text and AI agree", "text", "AI", or "AI disagreed; text used", derived from `source` and `mismatch`.
- **FR-007**: The callback panel MUST show the masked number with "number on file (vendor master), not from the email", the stepper built from `verification.events`, the transcript with classifier and verifier chips, the last-four result, and a SIMULATED badge when `verification.source` is simulated.
- **FR-008**: The analyst note MUST render in the AI color, labeled "AI-written explanation; doesn't change the decision", and show a "Rules fallback" chip when the rules wrote it.
- **FR-009**: Actions MUST follow the server-computed `actions` flags: "Approve payment" and "Reject" when `can_review`; "Call vendor again" when `can_retry_call`; "Try to make the AI pay" (held-color outline) when `can_redteam`; Simulate controls when `can_simulate`. No action is shown when its flag is false.
- **FR-010**: The red-team dialog MUST state the blocking layer (plugin, ledger or agent refused) and the reason returned by the API, and the trace sheet MUST open automatically.
- **FR-011**: The payment card MUST show amount, masked destination, method `ACH-CCD`, effective date and who released it (agent or policy).
- **FR-012**: The destination card MUST show the account on file and, when present, the requested account, with changed parts highlighted in the held color; routing numbers in full, account numbers masked (PLAN.md §7.6).

**Tabs (PLAN.md §14.9)**

- **FR-013**: Payments MUST show the KPI strip from `/api/stats` and the ledger from `/api/payments`; the ACH batch download is P3.
- **FR-014**: Vendors MUST show the vendor master and bank-change history from `/api/vendors`.
- **FR-015**: Audit log MUST show a "Chain verified" header only when `chain_ok` is true, the entries with short hashes, and the export link (P1).
- **FR-016**: DevRev cases MUST list cases from `/api/change-cases` and open one by id.
- **FR-017**: Demo controls MUST appear only when health reports `demo_mode`, and MUST offer Reset demo (with a confirmation), AI live/off, and Simulate yes/no with a last-four input for the selected invoice.

**Header and global behavior (PLAN.md §14.9, §14.10)**

- **FR-018**: The header MUST show health dots with tooltips (db, model, twilio, storage), "Running on" plus `deploy_label`, the inference latency, the theme toggle, and "AI: live" or "AI: off (rules only)", all from `/api/health`.
- **FR-019**: Toasts MUST appear only after a user action, with the copy "Demo reset", "Payment approved" and "Calling the vendor again"; background events show in the panels, never as toasts.
- **FR-020**: j and k MUST move through the queue, Enter MUST open a case, and focus rings MUST always be visible.
- **FR-021**: The dashboard MUST meet the PLAN.md §14.10 quality bar: readable from 5 m at 1280×720 and 125% zoom, body text at least 16 px, text contrast at least 4.5:1 in both themes, status never by color alone, `prefers-reduced-motion` respected, zero console errors, zero third-party network requests.
- **FR-022**: The light theme MUST be the default (PLAN.md §14.5), and the chosen theme MUST persist.

**Modes, serving and contract (PLAN.md §14.5, §17.1)**

- **FR-023**: Fixtures mode (PLAN.md §14.5, `VITE_API_MODE=fixtures`) MUST keep working for offline demos, including the development-only scenario player; live mode MUST call `/api` on the same origin.
- **FR-024**: In production the built dashboard MUST be served at `/` by the API process, mounted after the API routes, with unknown paths falling back to the app shell; in development the app MUST reach the API through the same relative `/api` path.
- **FR-025**: Nothing MUST load from a CDN at runtime.
- **FR-026**: A fixtures contract test (`tests/test_fixtures_contract.py`, PLAN.md §17.1) MUST validate every file in `web/src/fixtures/` and the output of `scripts/export_fixtures.py` against the InvoiceDetail shape in PLAN.md §7.6, without network access.
- **FR-027**: The screenshot set in `web/snapshots/` MUST be regenerated against the live-wired build (PLAN.md §14.7 step 5) and compared with the spec 004 prototype before each rehearsal.
- **FR-028**: Errors shown to the user MUST say what happened and what to do next; the empty queue MUST say "Load a sample invoice to start." (PLAN.md §14.6).

### Key Entities *(include if feature involves data)*

- **Queue row**: one invoice in the list (`GET /api/invoices`): id, created time, vendor name, display amount, tier, points, status, hold reason, source. Newest first.
- **InvoiceDetail**: the open case (PLAN.md §7.6), with its email, extracted fields, vendor, risk, destination, analyst report, verification, payment, memo, trace, audit entries, `actions` flags and `ai_fallback`. The UI depends on these exact keys.
- **Health**: db, model (ok, latency, checked time), twilio configured, storage ok, `demo_mode`, `ai_mode`, `deploy_label`.
- **Stats**: released cents, held cents, invoices, calls placed, median decision seconds since the last reset.
- **Payment, Vendor, Change case, Audit entry**: the tab data from `/api/payments`, `/api/vendors`, `/api/change-cases` and `/api/audit` (with `chain_ok` and `broken_at`).
- **Demo command**: reset (optionally including change cases), simulate answer (subject, yes/no, last four), AI mode (live/off).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every pipeline step the backend reaches is visible in the open case within 1 second of landing, measured against the audit timestamps, for all five demo scenarios.
- **SC-002**: The full PLAN.md §19.1 3-minute story runs end to end on the live API in light mode at 1280×720 and 125% zoom, with the real call or the simulated fallback, with no step skipped and no page reload.
- **SC-003**: Every fixture file and the exported fixtures validate against the live InvoiceDetail shape; the contract test passes with zero credentials.
- **SC-004**: Zero console errors and zero requests to third-party hosts during a complete story run, in both live and fixtures modes.
- **SC-005**: A reviewer at 5 m can read the stamp, the decision sentence, the top three risk flags and the callback verdict on the projector in both themes; text contrast measures at least 4.5:1.
- **SC-006**: Each of the three demo controls (reset, AI toggle, simulate) produces its visible effect in the panels and header within one polling interval and shows its toast only after the click.
- **SC-007**: Fixtures mode plays all scenario steps with the backend stopped, and the snapshot set is regenerated and reviewed before the first rehearsal.

## Dependencies & Scope

- **Owner**: Builder A's UI session (PLAN.md §14, §18 rows A7 and A8).
- **Depends on**: spec 004 (the chosen design, fixtures, scenario player and snapshot script) and spec 005 (the live pipeline, routes and `actions` flags in PLAN.md §7.6). Spec 006 (voice) feeds the real callback; the simulated fallback covers it when absent.
- **Out of scope**: new design work. The visual direction, gallery winners and layout were chosen in spec 004 and recorded in `docs/design/decisions.md`; this spec wires them to live data and polishes, it does not redesign. New endpoints or panels not in PLAN.md are out of scope; any data gap is raised as a §7 contract change with both builders.
- **PLAN.md sections covered**: §14.5 (modes and serving), §14.9 (behavior on the live API), §14.10 (quality bar), §7.6 (HTTP API, InvoiceDetail, `actions` rules), §17.1 (`test_fixtures_contract.py`), §19.1 and §19.2 (pitch and pre-demo checklist), §18 (A7, A8).

## Assumptions

- The spec 005 API is reachable in demo mode with the PLAN.md §7.6 shapes frozen; the UI never redesigns those contracts (constitution principle I).
- The audit export link targets the entries already returned by `GET /api/audit` for the selected invoice; no separate export endpoint is defined in §7.6, and none is added here.
- Polling cadences are fixed as written in PLAN.md §14.9; no push channel is introduced.
- The fallback when inference is slow is the AI-off toggle (PLAN.md §19.2); the dashboard shows the rules-only state rather than waiting on the model.
- The presenter's browser has basic auth cached, notifications off and the light theme selected before going on stage (PLAN.md §19.2); the dashboard does not manage those.
- Spec kit priorities P1, P2 and P3 in this document map to PLAN.md P0, P1 and P2 (constitution principle X).
