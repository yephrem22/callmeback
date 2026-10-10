# Feature Specification: DevRev Connector and verify-change-request Skill

**Feature Branch**: `008-devrev-connector`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "A reusable DevRev Computer capability for support and finance teams: verify a request to change a customer account's billing contact, payment details, remit-to address or admin contact before anyone acts on it.
Using only Enterprise-Bench data, it:
- finds the account and lists its contacts of record;
- runs disclosed checks on the sender and the request text;
- searches for corroborating evidence;
- writes an evidence-backed brief naming who to call back, taken from the records and never from the request.
After a preview and explicit approval, it opens an idempotent callback case in Call Me Back.
P1: It works for a second authorized teammate on a different account.
P1: It handles missing data, ambiguous accounts and a disconnected connector honestly.
Details are in PLAN.md §15."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify a change request and get an evidence-backed brief (Priority: P1)

A support or finance teammate receives an email asking to change a customer account's billing contact, payment details, remit-to address or admin contact. In DevRev Computer they ask whether the request is legitimate. The `verify-change-request` skill (PLAN.md §15.4) resolves the account in Enterprise-Bench, lists the contacts of record, runs the disclosed checks of PLAN.md §15.3 on the sender and the request text, searches for corroborating evidence, and writes a brief that names the contact of record to call back. The callback target always comes from the records, never from the request.

**Why this priority**: This is the capability being submitted to the DevRev Computer challenge (PLAN.md §3, §15.1). Without the brief there is nothing to register, reuse or demo; the read-only skill and check tools are the last DevRev items in the §4 cut order.

**Independent Test**: With the connector registered and the skill installed, a single user can paste a request for one account in a fresh conversation and receive a brief with signals, rules, points, evidence and a callback contact. Delivers value with no case ever created.

**Acceptance Scenarios**:

1. **Given** the skill is installed, **When** the user asks "Is this request to change ACCOUNT's billing contact legit?", **Then** the skill runs and returns a brief in the §15.4 output format (verdict, signals, records of truth with source references, call back, missing or uncertain, next step). (§15.6 test 1)
2. **Given** the skill is installed, **When** the user says "Someone emailed asking us to update ACCOUNT's remit-to details. Check it.", **Then** the skill runs and returns a brief. (§15.6 test 2)
3. **Given** the skill is installed, **When** the user asks "Explain how MCP connectors work.", **Then** the skill does not run. (§15.6 test 3)
4. **Given** a sender domain built from a real documented account domain with one character swapped, **When** the request is checked, **Then** the brief reports `SENDER_DOMAIN_LOOKALIKE` (40 points) with its rule and evidence. (§15.6 test 5)
5. **Given** a sender address at a free-mail provider, **When** the request is checked, **Then** the brief reports `FREE_MAIL_SENDER` (20 points). (§15.6 test 6)
6. **Given** the request text names a person, phone number or email to contact, **When** the brief is written, **Then** the callback contact is a contact of record (preferring a billing/finance title per §15.3) and never the person, number or email from the request.
7. **Given** any check response, **When** it is shown, **Then** every signal carries its rule, points and evidence, and the response carries the §15.3 notice that this is rules-based screening, not a fraud verdict.

---

### User Story 2 - A second authorized teammate uses it on a different account (Priority: P1)

A second teammate in the same isolated team org accepts the invite, adds a personal connection to the connector, and runs the skill on a different account in a fresh conversation. They get a valid brief without any help from the author.

**Why this priority**: Reusability is 25% of the proposed DevRev rubric (PLAN.md §3) and the DevRev demo is driven by the second user (§15.7). It proves the capability is an org asset, not a personal setup.

**Independent Test**: After org-wide publication (§15.5 steps 6-7), Builder A runs the skill on an account the author never used and records the result in `devrev/TESTS.md` row 11.

**Acceptance Scenarios**:

1. **Given** the connector is registered with the §15.5 settings and all 9 tools were discovered, **When** the second user adds a personal connection and runs the skill on a different account, **Then** they receive a valid brief with signals, records of truth and a callback contact. (§15.6 test 11)
2. **Given** the registration's Access tab, **When** an admin reviews it, **Then** every read, check and preview tool is set to *Always allow* and only `create_verification_case` is *Needs approval*.
3. **Given** the deployed connector, **When** the smoke test runs against the public endpoint with the pinned export, **Then** auth rejection, initialize, tool discovery, source read and the path boundary all PASS (§15.5 step 1).

---

### User Story 3 - Honest handling of missing data, ambiguity and outages (Priority: P1)

When the records are incomplete, the account name matches several records, or the connector is unavailable, the skill says so plainly and never fills the gap with a guess.

**Why this priority**: Correctness and evidence are 25% of the rubric (§3), and the constitution's Fail Closed principle requires a "not documented" answer rather than an invented one. A confident wrong brief is worse than none.

**Independent Test**: Run §15.6 tests 4, 7 and 10 against the deployed connector; each produces the stated honest message and no fabricated contact, phone or verdict.

**Acceptance Scenarios**:

1. **Given** an account name that plausibly matches more than one record, **When** the skill resolves the account, **Then** it shows the candidates with evidence and asks which one, and never guesses. (§15.6 test 4)
2. **Given** an account whose contacts of record have no documented phone number, **When** the brief is written, **Then** the contact's phone is reported as "not documented; verify through a known channel" and no number is invented. (§15.6 test 7)
3. **Given** the connector is disabled or the token is rejected, **When** the skill is invoked, **Then** it states the dependency is unavailable and stops, producing no verdict. (§15.6 test 10)
4. **Given** an account with no contacts of record, **When** the check runs, **Then** `callback_target` is null, the gap is listed under `missing_evidence`, and the brief recommends verification through a known channel.
5. **Given** any request, **When** a verdict is written, **Then** the strongest positive verdict is "Consistent with records (still verify)"; the skill never declares a request legitimate.

---

### User Story 4 - Open an idempotent callback case after preview and approval (Priority: P2)

After reading the brief, the teammate asks to open a callback case. The skill shows the exact preview, and only after explicit approval creates the case in Call Me Back, where it appears in the dashboard's DevRev cases tab. Submitting the same request again returns the existing case instead of a new one.

**Why this priority**: Case creation is the "acts only with approval" half of the story and the finale of the DevRev demo (§15.7), but PLAN.md §4 cuts create/get case before the read-only skill, so it ranks below the brief.

**Independent Test**: Approve one create, then re-run the identical request; the second response reports `duplicate: true` with the same case id, and the dashboard shows exactly one case.

**Acceptance Scenarios**:

1. **Given** a completed brief, **When** the user asks to open a case, **Then** the skill shows the exact case preview and the sandbox note, and no write has occurred.
2. **Given** the preview is shown, **When** the user declines, **Then** no case exists in the dashboard. (§15.6 test 8)
3. **Given** the preview is shown, **When** the user explicitly approves, **Then** a case is created with status `OPEN`, and the skill reports it as new with its dashboard path.
4. **Given** a case was created, **When** the same account, sender, change type and request text are submitted again, **Then** the response reports `duplicate: true` with the same `case_id`. (§15.6 test 9)
5. **Given** a create request whose supplied idempotency key does not match the one recomputed from its inputs, **When** it is submitted, **Then** it is rejected and no case is created.
6. **Given** an existing case, **When** the user later asks about its status, **Then** the skill returns the case id, status, outcome, call details (or none) and last update time.

---

### User Story 5 - Sandbox callback from a change case (Priority: P3)

An operator places a sandbox verification call from an open change case. The call is routed only to the team demo line, and the answer updates the case status without touching invoices or the payment ledger.

**Why this priority**: PLAN.md §4 lists this under P2 ("only if ahead"); it is a demo flourish, not a judged requirement.

**Independent Test**: Trigger the call route on an `OPEN` case in sandbox mode; the case moves through `CALLING` to one of `CONFIRMED`, `DENIED`, `UNCLEAR` or `NO_ANSWER` using the change-case script of PLAN.md §12.3, and the invoices and ledger are unchanged.

**Acceptance Scenarios**:

1. **Given** an `OPEN` change case, **When** a sandbox call is placed, **Then** the number dialed is the team demo line, never a number from Enterprise-Bench or the request, and the case shows "sandbox: routed to the team demo line".
2. **Given** a sandbox call completes, **When** the answer is classified, **Then** only `change_cases.status` changes; no invoice or ledger row is touched.

---

### Edge Cases

- Sender domain is both a lookalike and undocumented: the lookalike rule fires per §15.3; the brief still lists every signal that applies with its evidence.
- Request text contains instructions aimed at AI assistants: `AI_DIRECTED_TEXT` is reported at 0 points and the text is still treated as untrusted input.
- Contacts have emails but no phones: `phone_documented` is false, each `phone` is null, and the brief says "not documented".
- `requested_change` is `other`: neither change-type rule fires; the tier and `callback_required` follow the remaining signals.
- The pinned export has not arrived: development uses the public Enterprise-Bench release with its own dataset version (§15.2); the demo and `TESTS.md` use only the SE's pinned export.
- The dataset version changes between preview and create: the idempotency key differs, so the create is rejected and the user must preview again.
- Corroborating evidence uses similar wording but is not about this account's change: the brief says what was found and what was not; similar wording is not proof.
- Demo reset: change cases survive the dashboard's demo reset unless explicitly included (PLAN.md §7.6).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The connector MUST expose the three starter evidence tools unchanged (`list_sources`, `search_evidence`, `read_evidence`) plus six new tools per PLAN.md §15.3: `find_accounts`, `get_contacts_of_record`, `check_change_request`, `preview_verification_case` and `get_verification_case` (access mode *Always allow*), and `create_verification_case` (access mode *Needs approval*). Tool names MUST stay stable after registration.
- **FR-002**: The only business data MUST be Enterprise-Bench, from the export DevRev provides. The connector MUST NOT read Call Me Back's demo vendor master and MUST NOT enrich from the web. The request text is user input, not business data. The data folder is mounted read-only and never includes tests, grading files or answers (§15.2).
- **FR-003**: `check_change_request` MUST apply exactly the disclosed rules of PLAN.md §15.3: `SENDER_DOMAIN_LOOKALIKE` 40, `SENDER_DOMAIN_UNDOCUMENTED` 25, `FREE_MAIL_SENDER` 20, `SENDER_NOT_CONTACT_OF_RECORD` 10, `PAYMENT_DETAILS_CHANGE` 50, `CONTACT_CHANGE` 30, `URGENCY` 10, `AVOID_VERIFICATION` 15, `AI_DIRECTED_TEXT` 0. Every signal MUST carry its `code`, `points`, `rule` and `evidence`, and every response MUST include `rules_version` and the §15.3 notice.
- **FR-004**: Tiers MUST follow PLAN.md §10.2 (GREEN < 20 ≤ YELLOW < 50 ≤ RED, uncapped points). `callback_required` MUST be true when the tier is not GREEN or when `PAYMENT_DETAILS_CHANGE` fired.
- **FR-005**: `callback_target` MUST be chosen from the contacts of record, preferring a billing/finance title per §15.3, otherwise the first documented contact. It MUST NEVER be a person, number or email named in the request text. With no contacts it MUST be null and listed in `missing_evidence`.
- **FR-006**: When a contact has no documented phone, `phone` MUST be null, `phone_documented` MUST be false, and the brief MUST say "phone not documented; verify through a known channel". A phone number MUST never be invented.
- **FR-007**: `find_accounts` MUST return candidates with `source_ref` and an `ambiguous` flag; when ambiguous, the skill MUST present the candidates and ask rather than guess.
- **FR-008**: Every record-backed claim MUST cite a `source_ref` of the form `{path, sha256, line_start, line_end}`, the same format as the starter's `read_evidence`.
- **FR-009**: `preview_verification_case` MUST perform no write and MUST return the `idempotency_key`, the exact case content and the sandbox note.
- **FR-010**: Case creation MUST be idempotent: the key is derived from account id, lower-cased sender email, requested change, whitespace-normalized request text and the dataset version (§15.3). The same request twice MUST yield the same `case_id` with `duplicate: true`. `create_verification_case` MUST recompute the key and reject a mismatch.
- **FR-011**: Cases MUST be written through the internal API of PLAN.md §7.5 (`POST /internal/change-cases`, `GET /internal/change-cases/{case_id}`) into the `change_cases` table of §7.2, with `created_by` = `devrev`. The internal routes MUST be unreachable from outside the VM.
- **FR-012**: The connector MUST require a bearer token; an unauthenticated request MUST be rejected with 401 (§0.4). The token value MUST never appear in specs, logs, docs or chat.
- **FR-013**: The skill MUST be the `verify-change-request` SKILL.md of PLAN.md §15.4, verbatim, with the folder name matching `name` and the description under 1,024 characters with no angle brackets in the frontmatter.
- **FR-014**: The skill MUST stop with an honest dependency message, and no verdict, when the connector is unavailable or unauthorized. Its strongest positive verdict MUST be "Consistent with records (still verify)".
- **FR-015**: Registration MUST follow PLAN.md §15.5 (name, slug, description, token, access modes, personal test, org-wide publish only inside the isolated team org, second-user connection, resync after tool changes).
- **FR-016**: The eleven tests of PLAN.md §15.6 MUST be run against the pinned export and recorded in `devrev/TESTS.md` with the columns test, prompt, account, expected, observed, pass/fail.
- **FR-017**: (P3) A sandbox call from a change case MUST dial only `DEMO_VENDOR_PHONE`, use the change-case script of §12.3, update only `change_cases.status`, and never touch invoices or the ledger.
- **FR-018**: The connector MUST run with no DevRev credentials and no pinned export present (public release or local fixture selected by environment), so the test suite passes with zero credentials (constitution V).

### Key Entities *(include if feature involves data)*

- **Account**: an Enterprise-Bench CRM account with id, name, documented domains and a source reference. Resolved by `find_accounts`.
- **Contact of record**: a documented person on an account with name, title, email, phone (may be null) and source reference. The only permitted source of a callback target.
- **Change request**: user input consisting of account, sender email, request text and requested change (`billing_contact`, `payment_details`, `remit_address`, `admin_contact` or `other`). Untrusted.
- **Signal**: one fired check rule with code, points, rule text and evidence; aggregated into points, tier and `callback_required`.
- **Verification brief**: the skill's output in the §15.4 format: verdict, signals, records of truth, call back, missing or uncertain, next step.
- **Change case**: the persisted callback case (PLAN.md §7.2 `change_cases`) keyed by `idempotency_key`, with status `OPEN` → (P3) `CALLING` → `CONFIRMED` | `DENIED` | `UNCLEAR` | `NO_ANSWER`, plus `CLOSED`.
- **Source reference**: `{path, sha256, line_start, line_end}` pointing into the pinned export, with its dataset version.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The smoke test passes against the deployed public endpoint with the pinned export: auth rejection, initialize, tool discovery, source read and path boundary all PASS.
- **SC-002**: DevRev's tool discovery lists all 9 tool names after setup, and the Access tab shows exactly one tool (`create_verification_case`) as *Needs approval*.
- **SC-003**: Approving a create and then submitting the identical request returns `duplicate: true` and the same `case_id`; the dashboard shows one case, not two.
- **SC-004**: A second user, on a different account, in a fresh conversation, receives a valid brief (verdict, signals with rules, records of truth with source references, callback contact).
- **SC-005**: The negative trigger prompt ("Explain how MCP connectors work.") does not run the skill.
- **SC-006**: All eleven §15.6 tests are recorded in `devrev/TESTS.md` with observed results, and rows 1-11 pass against the pinned export.
- **SC-007**: In every recorded test, the callback contact named in the brief appears in the contacts of record and never matches a name, number or email from the request text.
- **SC-008**: In the no-phone test, the brief contains "not documented" and no digits that are absent from the records.
- **SC-009**: With the connector disabled, the skill's reply contains a dependency message and no verdict line.

## Dependencies & Scope

- **Owner**: Builder B (PLAN.md §0.8, §18 milestones B6-B9).
- **Depends on**: spec 002 cloud-infra (the VM, the public host and the `/mcp` route) and spec 003 core-engine (the shared lookalike and phrase rules, tier thresholds); playground access for both builders, the admin and publisher roles, and the Enterprise-Bench export with its version manifest from the DevRev SE (§0.4, §15.2).
- **Out of scope**: making the requested change itself; sending messages; general account research; any use of the demo vendor master or web enrichment; dialing any Enterprise-Bench number; the dashboard's DevRev cases tab UI (spec 007) beyond the API it reads; the Strands `MCPClient` reuse of the check tools (P2 in §4).
- **PLAN.md sections covered**: §15 in full (§15.1-§15.7), the internal API in §7.5, the `change_cases` table in §7.2, the DevRev row of §3, the DevRev row of §0.4, the change-case script in §12.3 (P3), and milestones B6-B9 in §18.

## Assumptions

- The Enterprise-Bench field mapping (account id, name, domain, contact name, title, email, phone) is settled by `/speckit-clarify` after `scripts/eb_inspect.py` runs on the pinned export (milestone B6); until then development uses the public release with its own dataset version, per PLAN.md §15.2.
- The DevRev SE provides playground invites for both builders, admin and publisher roles, and the pinned export in time for B6; if the export is late, the brief and check tools are still demonstrable on the public release, but `TESTS.md` and the demo wait for the pinned export.
- CRM contacts may lack phone numbers entirely; this is acceptable and handled by the "not documented" path, not a blocker.
- The proposed rubric weights in PLAN.md §3 (usefulness, reusability, correctness/evidence, operational quality) are the judging basis; priorities in this spec follow them and the §4 cut order.
- Spec priority labels P1, P2 and P3 correspond to PLAN.md P0, P1 and P2 (constitution X); the whole DevRev entry is PLAN.md P1, with create/get case cut before the read-only skill and the sandbox call PLAN.md P2.
- Sponsor starter code is adapted with credit in the README (constitution XI); its three evidence tools are kept unchanged.
