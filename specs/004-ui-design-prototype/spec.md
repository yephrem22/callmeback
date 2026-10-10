# Feature Specification: UI Design Prototype

**Feature Branch**: `004-ui-design-prototype`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "A design-first prototype of the Call Me Back dashboard, built before the backend is wired.
Users:
- Primary: an accounts-payable specialist at a mid-size company, working a queue of invoices under time pressure.
- Secondary: the controller who reviews exceptions and answers to auditors.
- Also: hackathon judges watching on a projector.
In order of visual weight, the screen must answer: can this money move; why or why not; what is being done to verify it (a live phone call); what evidence backs it; and what the AI did.
P1: A short user and pattern research note. Then a gallery of at least ten candidate components and charts relevant to this product. Each candidate shows what it shows, which user decision it serves, the data it needs from the API and a code snippet, in two variants. The humans pick the winners.
P1: A clickable prototype that plays the demo story from fixture data: normal invoice paid; fraud invoice called, then held; bank change confirmed; review approved; unknown vendor held.
P2: Light and dark themes, and keyboard navigation of the queue.
Details are in PLAN.md §14."

## User Scenarios & Testing *(mandatory)*

The dashboard is designed before it is wired (PLAN.md §14, §14.7). This spec covers the research note, the candidate gallery, the human gate that picks the winners, and a clickable prototype that rehearses the demo story on fixture data. Spec 007 connects the chosen design to the live API. Spec Kit priorities P1, P2 and P3 below map to PLAN.md P0, P1 and P2 (constitution principle X).

### User Story 1 - Research note and candidate gallery (Priority: P1)

Builder A spends 15 minutes researching AP workflows, BEC callback procedures and how leading bill-pay and fraud tools present risk, and records the three personas from PLAN.md §14.1, their top decisions, the patterns to borrow from PLAN.md §14.4, and sources in `docs/design/research.md`. Then a development-only gallery renders every candidate from PLAN.md §14.8 on hand-written fixture data so both builders can compare them side by side (milestone U1, PLAN.md §18).

**Why this priority**: The gallery is the input to the human gate; without it nothing downstream can be chosen, and the prototype would be built on guesses rather than on the five questions the screen must answer (PLAN.md §14.2).

**Independent Test**: Open the gallery route in development mode and count the candidates. Each one renders from fixture data with all six parts listed in PLAN.md §14.7 step 2 and two variants. The research note exists and names the personas, decisions, patterns and sources. This delivers value on its own as a reviewed design catalogue.

**Acceptance Scenarios**:

1. **Given** the research pass is complete, **When** a builder opens `docs/design/research.md`, **Then** it names the AP specialist, the controller and the judges with their top decisions (PLAN.md §14.1), lists the patterns to borrow with where they come from (PLAN.md §14.4), and cites its sources.
2. **Given** the development build is running, **When** a builder opens the gallery route, **Then** it shows these fourteen candidates from PLAN.md §14.8: (1) Risk breakdown bar, (2) Risk meter, (3) Amount vs history, (4) Lookalike diff, (5) Destination card, (6) Callback stepper, (7) Transcript bubble, (8) Agent trace waterfall, (9) Audit chain list, (10) KPI strip, (11) Payments ledger table, (12) Decision stamp variants, (13) Queue rows, (14) Vendor change history.
3. **Given** any single candidate in the gallery, **When** a reviewer reads its card, **Then** it states what it shows, which user and decision it serves, the exact §7.6 fields it needs, the components it uses, a copyable code snippet, and it renders two variants side by side.
4. **Given** a candidate chart, **When** it is viewed, **Then** it follows the chart rules in PLAN.md §14.8: marks are labelled directly, color never carries meaning alone, status colors match the tokens in PLAN.md §14.6, numerals are tabular, there is no pie or 3D chart, and no value is readable only through a tooltip.
5. **Given** the gallery route, **When** the production build is made, **Then** the route is not served.

---

### User Story 2 - Human gate: both builders pick the winners (Priority: P1)

After the gallery is ready, work stops. Both builders spend 15 minutes reviewing the gallery together (milestone U2, PLAN.md §18) and record which candidate and which variant wins for each slot in `docs/design/decisions.md`. Only then does prototype work begin. Losing candidates stay in the gallery for later reference (PLAN.md §14.7 step 3, §23.4 notes).

**Why this priority**: The constitution requires small vertical slices with a stop-and-report between phases (principle X), and PLAN.md makes this gate explicit. Skipping it risks building the prototype on components one builder likes and the other cannot demo.

**Independent Test**: Verify that `docs/design/decisions.md` exists, lists a winner (candidate number and variant) for each design slot the prototype uses, and that no prototype file was created before its timestamp.

**Acceptance Scenarios**:

1. **Given** the gallery passes all User Story 1 scenarios, **When** the UI session reaches the end of milestone U1, **Then** it stops, reports what was built and how it was checked, and waits for the review rather than starting the prototype.
2. **Given** both builders review the gallery, **When** the 15 minutes end, **Then** `docs/design/decisions.md` records, for each slot in the layout of PLAN.md §14.3 (decision, risk, destination, callback, evidence, queue, trace, tabs), the winning candidate number, the winning variant and a one-line reason.
3. **Given** the decisions file is written, **When** the prototype is built, **Then** it uses only the recorded winners, and the losing candidates remain visible in the gallery route.

---

### User Story 3 - Clickable prototype plays the demo story on fixtures (Priority: P1)

Using the winners, Builder A assembles the dashboard layout of PLAN.md §14.3 and a development-only scenario player that steps through the demo story on fixture data, so the visuals of the 3-minute pitch (PLAN.md §19.1) are rehearsed before the backend exists (milestone U3, PLAN.md §18). After each phase the builder captures screenshots of every step in both themes at the projector viewport and fixes the top three issues (PLAN.md §14.7 step 5).

**Why this priority**: This is the thing the judges see. It is the only way to find layout and legibility problems while there is still time to change the §7.6 contract.

**Independent Test**: Run the prototype in fixtures mode, open the scenario player, and step through each of the five scenarios end to end. Every step renders from a fixture file that matches the §7.6 shape, and the decision, reasons, callback and evidence read in the visual order of PLAN.md §14.2.

**Acceptance Scenarios**:

1. **Given** the prototype in fixtures mode with an empty queue, **When** the page loads, **Then** the case area reads "Load a sample invoice to start." and the header shows the health dots, theme control and AI mode indicator described in PLAN.md §14.3.
2. **Given** the scenario player, **When** a builder plays "Acme: normal invoice", **Then** the queue shows the invoice, the stamp reads PAID in the paid color with the one-sentence decision, there are no risk flags, the destination shows only the account on file, and the payment card appears.
3. **Given** the scenario player, **When** a builder plays "Acme: urgent bank change", **Then** the steps show in order: 160 risk points with the flags and the lookalike diff, the destination on file against the requested account with the changed parts highlighted, a CALLING stamp while the callback stepper fills from Dialing to Asked, the transcript "No, we never changed banks" with its classifier and verifier labels, then a HELD stamp with "Held. The vendor said no on the 10:42 call." and the red-team action available.
4. **Given** the scenario player, **When** a builder plays "Heartland: legitimate bank change", **Then** the callback steps end in a confirmed answer with the last-four check shown as passed, the stamp reads PAID, and the vendor change history shows the before and after accounts marked "verified by callback".
5. **Given** the scenario player, **When** a builder plays "Prairie Cloud: higher than usual", **Then** the stamp reads REVIEW with "Needs review: the amount is 2.1 times usual.", the amount-vs-history view highlights this invoice against the median, "Approve payment" and "Reject" are offered, and the next step shows PAID.
6. **Given** the scenario player, **When** a builder plays "Unknown vendor", **Then** the stamp reads HELD with "Held. No vendor record, so there's no trusted number to call.", no callback panel is shown, and the review and retry actions are absent.
7. **Given** any step of any scenario, **When** a reviewer opens the evidence area, **Then** the email, extracted fields, audit trail and analyst note are each reachable, the analyst note is rendered in the AI color and labelled as AI-written, and the agent trace opens as a side sheet on request.
8. **Given** a case reaches a decision, **When** the stamp appears, **Then** it presses in once as described in PLAN.md §14.6, and it does not animate when the viewer prefers reduced motion.
9. **Given** the snapshot script, **When** a builder runs it, **Then** it writes one screenshot per scenario step per theme at 1024×576 into `web/snapshots/`, and the builder records the top three issues found and fixes them before reporting the phase done.

---

### User Story 4 - Light and dark themes (Priority: P2)

A viewer switches between light, dark and system themes from the header. Light is the default because projectors wash out dark themes; the dark theme uses the ink-navy palette from PLAN.md §14.6 with status colors lightened to keep text legible.

**Why this priority**: Required by constitution principle IX, but the demo runs in light mode, so it follows the P1 stories.

**Independent Test**: Toggle the theme at each scenario step and confirm every element remains legible and every status still carries a word and an icon.

**Acceptance Scenarios**:

1. **Given** a first visit, **When** the page loads, **Then** the light theme is applied and the choice persists across reloads once changed.
2. **Given** the dark theme, **When** any scenario step is shown, **Then** all text meets 4.5:1 contrast and all status icons meet 3:1 against their background, using the tokens in PLAN.md §14.6.

---

### User Story 5 - Keyboard navigation of the queue (Priority: P2)

An AP specialist working the queue moves between invoices with j and k, opens a case with Enter, and always sees where focus is (PLAN.md §14.4 triage-list pattern, §14.9 keyboard rules, §14.10).

**Why this priority**: It serves the primary user's speed but is not needed to tell the demo story.

**Independent Test**: With several fixture invoices loaded, navigate the whole queue and open a case without touching the mouse.

**Acceptance Scenarios**:

1. **Given** focus is in the queue, **When** the user presses j or k, **Then** the highlighted row moves down or up with a visible focus ring, and Enter opens the highlighted case.
2. **Given** any focusable control on the page, **When** it receives keyboard focus, **Then** a focus ring in the ledger color is visible.

---

### Edge Cases

- A fixture scenario needs a value that the §7.6 InvoiceDetail does not carry: the builder does not add the field to the fixture; they raise a contract change with both builders, ideally before spec 003's first phase freezes the contracts (PLAN.md §14.7 step 4, constitution principle I).
- `destination.requested` is null (the normal Acme and Prairie invoices): the destination shows only the account on file and no change highlight.
- `risk.lookalike` is null (every scenario except the fraud invoice): the lookalike diff is not rendered.
- `vendor.history` is empty (the unknown vendor): the amount-vs-history view is omitted rather than drawn with no points.
- A flag has 0 points (AI_DIRECTED_TEXT, PHONE_IN_EMAIL on the fraud invoice): it appears as a note with an information icon, not as a weighted bar segment.
- `payment` is null: no payment card is shown; the stamp alone carries the decision.
- `verification.source` is simulated: a SIMULATED label is shown beside the callback.
- The viewer has `prefers-reduced-motion` set: the stamp appears without animation.
- The queue is empty: the case area reads "Load a sample invoice to start." and no stamp is shown.
- The viewport is 1024×576: nothing in the case area needs horizontal scrolling and the stamp, decision sentence and risk points remain visible without scrolling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The research note `docs/design/research.md` MUST record the three personas and their top decisions (PLAN.md §14.1), the patterns to borrow (PLAN.md §14.4) and the sources consulted, produced within a 15-minute research pass.
- **FR-002**: A development-only gallery route MUST render all fourteen candidates of PLAN.md §14.8 on fixture data; it MUST NOT be served in the production build.
- **FR-003**: Each gallery candidate MUST display what it shows, which user and decision it serves, the exact §7.6 fields it needs, the components it uses, a copyable code snippet, and two variants.
- **FR-004**: Every chart in the gallery and prototype MUST follow the chart rules in PLAN.md §14.8 and use the status tokens of PLAN.md §14.6.
- **FR-005**: Work MUST stop after the gallery for the human gate (milestone U2); winners and variants MUST be recorded in `docs/design/decisions.md` before any prototype work begins, and losing candidates MUST stay in the gallery.
- **FR-006**: The prototype MUST follow the layout and reading order of PLAN.md §14.2 and §14.3: decision first and largest, then reasons and destination, then the callback, then evidence, with the analyst note and trace secondary and collapsible.
- **FR-007**: The prototype MUST read all data from fixture files when in fixtures mode, with one file per scenario step, and MUST make no network requests in that mode.
- **FR-008**: Fixtures MUST match the InvoiceDetail shape in PLAN.md §7.6 key for key, and list, stats, payments and vendors fixtures MUST match the corresponding response shapes in the §7.6 table. Fixtures MUST NOT introduce fields that §7.6 lacks.
- **FR-009**: A development-only scenario player MUST step through the five demo-story scenarios in PLAN.md §19.1 and §14.7: Acme normal paid; Acme fraud called then held; Heartland bank change confirmed and paid; Prairie reviewed then approved; unknown vendor held. Final states MUST match PLAN.md §8.4.
- **FR-010**: Each scenario step MUST be addressable by URL query (scenario, step and theme) so the snapshot script and a presenter can open any state directly.
- **FR-011**: The decision MUST appear as the stamp described in PLAN.md §14.6 (PAID, HELD, REVIEW, CALLING) with the one-sentence decision copy of PLAN.md §14.9, and MUST respect `prefers-reduced-motion`.
- **FR-012**: Routing and account numbers MUST render as check lines per PLAN.md §14.6, with the changed parts highlighted in the held color and account numbers masked to their last four digits.
- **FR-013**: Anything written by an AI (analyst note, trace labels) MUST use the AI color and be labelled as AI-written so it is never mistaken for a rule-based fact.
- **FR-014**: Status MUST always be conveyed with a word and an icon in addition to color (PLAN.md §14.10, constitution principle IX).
- **FR-015**: Copy MUST follow the rules in PLAN.md §14.6: plain verbs, sentence case except the stamp, no arrows on buttons, no middle-dot meta strings, and the empty-queue message "Load a sample invoice to start."
- **FR-016**: The prototype MUST offer light, dark and system themes with light as the default, persisted across reloads, using the color tokens and dark-theme values of PLAN.md §14.6.
- **FR-017**: The queue MUST support j and k to move and Enter to open, with a visible focus ring on every focusable element.
- **FR-018**: A snapshot script MUST capture every scenario step in both themes at a 1024×576 viewport into `web/snapshots/`; after each phase the builder MUST review the screenshots and fix the top three issues before reporting the phase done.
- **FR-019**: The project setup MUST follow PLAN.md §14.5, and the typecheck, lint and build checks named there MUST pass before each commit.
- **FR-020**: Nothing MUST load from a third-party host at runtime; fonts and all assets are bundled (PLAN.md §14.5, constitution Technical Constraints).

### Key Entities *(include if feature involves data)*

- **Persona**: one of the three users in PLAN.md §14.1 with their context and top decisions; recorded in the research note.
- **Gallery candidate**: one of the fourteen entries in PLAN.md §14.8: a number, name, the users it serves, the §7.6 fields it needs, two variants and a snippet.
- **Design decision**: a record in `docs/design/decisions.md` pairing a layout slot with a winning candidate number, variant and reason.
- **Fixture**: a static response matching a §7.6 shape (InvoiceDetail, invoice list, stats, payments, vendors), one file per scenario step.
- **Scenario**: an ordered list of steps for one of the five demo-story invoices, each step pointing at a fixture; the final step matches the PLAN.md §8.4 final state.
- **Snapshot**: a screenshot of one scenario step in one theme at 1024×576, stored in `web/snapshots/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The gallery contains at least 10 candidates (14 planned), and 100% of them render two variants and all six required parts.
- **SC-002**: `docs/design/research.md` and `docs/design/decisions.md` both exist; the decisions file names a winner for every layout slot used by the prototype, and the review that produced it took no more than 15 minutes of both builders' time.
- **SC-003**: All five demo-story scenarios play end to end from fixtures, and each final state matches PLAN.md §8.4.
- **SC-004**: At 1024×576, the stamp, the decision sentence and the risk points are readable from 5 m on a 1280×720 projector at 125% zoom, as judged by both builders from the snapshots.
- **SC-005**: Body text is at least 16 px everywhere; text contrast is at least 4.5:1 and icon contrast at least 3:1 in both themes, verified for every status color.
- **SC-006**: Zero console errors and zero requests to third-party hosts while playing every scenario step in fixtures mode in both themes.
- **SC-007**: A full keyboard pass (j, k, Enter, Tab) reaches every queue row and every action without a mouse, with a focus ring visible at every stop.
- **SC-008**: The snapshot set in `web/snapshots/` covers every scenario step in both themes and is regenerated before each rehearsal; after each phase the top three issues found are recorded and fixed.
- **SC-009**: Fixtures introduce zero keys that are absent from PLAN.md §7.6; any data gap is logged as a contract-change request rather than a fixture field.
- **SC-010**: Typecheck, lint and build checks pass with zero errors.

## Dependencies & Scope

- **Owner**: Builder A's UI session, working in `web/` and `docs/design/` (PLAN.md §6, §14, §18 milestones U1–U3).
- **Depends on**: the §7.6 HTTP API contract only, for fixture shapes. No backend, model, telephony or storage service is required; nothing in this spec waits on credentials (constitution principle V).
- **Out of scope**: wiring to the live API, polling, live actions, toasts and tab data from the server, which are spec 007 (PLAN.md §14.9); any new screen, candidate or data field not in PLAN.md §14 or §7.6; the ACH batch download (PLAN.md §14.9, P2 of spec 007).
- **PLAN.md sections covered**: §14.1 through §14.8 and §14.10 in full; §7.6 as the fixture contract; §8.4 for final states; §18 milestones U1, U2, U3; §19.1 for the demo story; §23.4 for the prompt.

## Assumptions

- Fixtures are hand-written during U1 from the §7.6 example and the §8.4 vectors, and are replaced by real exports from `scripts/export_fixtures.py` once spec 003 produces them (PLAN.md §18, A3–A4). The shape does not change between the two.
- The §7.6 contract is frozen by spec 003's first phase around 11:30 (PLAN.md §18, A1); any gap the gallery exposes is raised before then where possible, and otherwise as a formal contract change agreed by both builders.
- The pre-run Heartland confirmation (PLAN.md §19.1) is represented in fixtures as a completed scenario whose final step shows the updated vendor master.
- Times on screen are shown in America/Chicago and money in integer cents formatted for display, per the constitution's technical constraints; fixtures carry the stored UTC form.
- The gallery route is kept in the codebase after the gate so spec 007 and later rehearsals can refer to it (PLAN.md §23.4 notes).
- The demo is presented in the light theme at 125% browser zoom on a 1280×720 projector; dark mode is verified but not rehearsed on stage.
