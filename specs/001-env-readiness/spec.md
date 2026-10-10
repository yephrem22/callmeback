# Feature Specification: Environment Readiness

**Feature Branch**: `001-env-readiness`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Environment readiness for Call Me Back. Two builders and their coding agents must never be blocked waiting on accounts or keys. Stories, in priority order:
P1: One command shows, for every integration (Akamai inference, Akamai Cloud API, public HTTPS URL, Object Storage, Twilio, DevRev and Enterprise-Bench data, optional AWS Bedrock, and the app's own generated secrets), whether it is READY, FAKE (fake mode selected), MISSING or FAILED, plus the next step to fix it, without ever revealing a secret value. It has three phases: build (report only), integrate, and demo.
P1: The whole codebase runs, and its tests pass, with zero credentials, because each integration has a fake mode chosen by an environment variable.
P1: One command generates the app's own secrets (internal API token, MCP token, dashboard password and its hash) into .env without overwriting existing values.
P2: A short, ordered setup runbook for humans, and guardrails that keep env files out of git and out of the agents' context, including in new git worktrees.
Out of scope: creating cloud resources, which is spec 002. The integration list, probes and phases are in PLAN.md §0.4 and §0.5; the variable list is in §7.1."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See readiness of every integration in one command (Priority: P1)

A builder, or the coding agent working for them, runs one readiness command and gets one row per integration from the PLAN.md §0.4 matrix (Akamai inference, Akamai Cloud API, public HTTPS URL, Object Storage, Twilio, DevRev and Enterprise-Bench data, optional AWS Bedrock, app secrets). Each row says READY, FAKE, MISSING or FAILED and gives the next step to fix it. No secret value is ever shown; at most the last four characters appear. The command runs in one of three phases, `build` (default, report only), `integrate` or `demo`, and its exit status tells the caller whether that phase's gate is met.

**Why this priority**: Credentials arrive on the organizers' schedule (constitution V). Without a single, safe, shared view of what is live, each builder and each agent re-discovers the state by hand, and the only alternative, printing `.env`, is forbidden (constitution VI). Both the T+20 Akamai key step in PLAN.md §0.2 and the 4 PM integration gate in §0.6 are defined in terms of this command.

**Independent Test**: On a laptop with an empty `.env`, run the command in the default phase: it exits 0 and every row is MISSING or FAKE. Then add one real value (for example the Akamai inference key) and re-run: only that row changes to READY. No code change is needed between the two runs (PLAN.md §23.1 Notes).

**Acceptance Scenarios**:

1. **Given** an empty or absent `.env`, **When** the command runs in the `build` phase, **Then** it prints every row from §0.4 as MISSING or FAKE with a next step, prints no secret characters, and exits 0.
2. **Given** a `.env` whose only app-secret values are the placeholders from the example file (a short token or the placeholder dashboard hash), **When** the command runs in the `build` phase, **Then** it reports those rows as FAILED with the next step "generate secrets" and exits 1, because the build phase fails only on malformed values (§0.4).
3. **Given** valid Akamai inference, public URL and Twilio settings but no Object Storage key, **When** the command runs in the `integrate` phase, **Then** it exits 0, because that phase requires only those three rows READY (§0.4); **When** it runs in the `demo` phase instead, **Then** it exits 1 and names each missing demo requirement (`AI_MODE=live`, `VOICE_MODE=twilio`, the MCP probe, the Enterprise-Bench version, Twilio balance of at least $10).
4. **Given** a Twilio account that is a trial, or whose balance is under $10, or whose number cannot make voice calls, **When** the Twilio row is probed, **Then** it is FAILED with the specific reason and no voice call has been placed.
5. **Given** the command is run any number of times without the explicit call-test option, **When** the Twilio probe runs, **Then** no outbound call is ever placed (§0.4).
6. **Given** a probe target that does not answer, **When** the command runs, **Then** that row is FAILED within the per-probe time limit, the remaining rows still run and print, and the command still exits by the phase rule.
7. **Given** any output mode, human table or machine-readable, **When** a row includes evidence about a secret (key, token, hash, auth token), **Then** no more than its last four characters are visible.

---

### User Story 2 - Build and test with zero credentials (Priority: P1)

A builder clones the repository, copies the example environment file, and the whole codebase runs and its tests pass with no credentials at all, because each integration is switched to its fake mode by an environment variable: `AI_MODE=off`, `VOICE_MODE=simulated`, `STORAGE_MODE=local`, `LLM_FALLBACK=none`, and development against the public Enterprise-Bench release for `EB_DATA_DIR` (PLAN.md §0.4 "Until it's live" column, §0.6, §15.2).

**Why this priority**: This is constitution V in full. Specs 003 to 009 start before any key is confirmed (PLAN.md §0.6); if the defaults did not select fake modes, every other session would be blocked at kickoff.

**Independent Test**: In a fresh checkout with the example environment copied unchanged (apart from generated app secrets), run the test suite with no network: it passes. Run the readiness command: every mode-selected integration shows FAKE, not MISSING or FAILED.

**Acceptance Scenarios**:

1. **Given** the committed example environment file, **When** a builder copies it to `.env` without editing, **Then** every mode variable in it selects the fake mode (`AI_MODE=off`, `VOICE_MODE=simulated`, `STORAGE_MODE=local`, `LLM_FALLBACK=none`) and every secret has an obviously fake value (§7.1).
2. **Given** an integration whose mode variable selects its fake mode, **When** the readiness command runs, **Then** that row is FAKE regardless of whether real credentials are also present.
3. **Given** no credentials and no network, **When** the test suite runs, **Then** all tests pass and nothing in them calls the network (constitution VIII); this includes this feature's own tests for masking, phase logic and the empty-`.env` build pass (§17.1, `test_check_env.py` row).
4. **Given** the example environment file, **When** it is compared with the variable list in PLAN.md §7.1, **Then** every variable in §7.1 is present with a comment, and no variable outside §7.1 is added.

---

### User Story 3 - Generate the app's own secrets safely (Priority: P1)

A builder runs one command and the app's own secrets (`INTERNAL_TOKEN`, `MCP_TOKEN`, and the dashboard password with its stored hash `DASH_PASS_HASH`) are written into `.env`. Values already present are never overwritten. The dashboard password itself is shown to the operator once and never stored; only its hash is written.

**Why this priority**: Spec 002 needs these secrets to deploy (§0.4, "Needed live by" column), the dashboard is behind basic auth from the first deploy, and the readiness command's build phase fails on a placeholder hash. Hand-generating a bcrypt hash that survives the quoting rules in §7.1 is error-prone, so this must be one command.

**Independent Test**: Run the command on an empty `.env`: the three secrets appear, the tokens are at least 32 characters, the hash is bcrypt in single quotes, and the password is printed once. Run it again: the file is byte-for-byte unchanged. The readiness command's app-secrets row turns READY.

**Acceptance Scenarios**:

1. **Given** a `.env` that lacks the app secrets or holds the example placeholders, **When** the command runs, **Then** `INTERNAL_TOKEN` and `MCP_TOKEN` are written with at least 32 characters each, `DASH_PASS_HASH` is a bcrypt hash written in single quotes (so its `$` signs survive, per the quoting rule in §7.1), and the plain password is displayed once.
2. **Given** a `.env` that already holds a valid value for any of these variables, **When** the command runs, **Then** that value is left exactly as it was and only the missing ones are filled in.
3. **Given** no `.env` exists yet, **When** the command runs, **Then** `.env` is created with the generated secrets and nothing else is lost or required.
4. **Given** the secrets were generated, **When** the readiness command runs in the `build` phase, **Then** the app-secrets row is READY ("present; tokens have 32+ characters; the hash is bcrypt", §0.4).

---

### User Story 4 - Runbook and guardrails for env files (Priority: P2)

A human teammate follows a short, ordered setup runbook that walks from a fresh clone through the Track B steps of PLAN.md §0.2, the tools in §0.3, and the readiness and secrets handling of §0.4 and §0.5. Repository guardrails keep `.env` and `.env.local` out of git, copy `.env` into every new Claude Code worktree, and stop agents from reading env files with their file-reading tool.

**Why this priority**: Valuable but not blocking: the P1 stories work without it. It prevents the two costly mistakes in a parallel build, a committed secret and a worktree that silently lacks `.env`, and it gives a newcomer one page instead of PLAN.md.

**Independent Test**: In a fresh clone, create `.env` with a dummy value, create a new worktree, and confirm: `.env` is not reported as untracked by git, `.env` exists in the new worktree, an agent's attempt to read `.env` or `.env.local` with its Read tool is denied while `.env.example` is readable, and the runbook's steps, followed in order, end at a build-phase pass of the readiness command.

**Acceptance Scenarios**:

1. **Given** a checkout containing `.env`, `.env.local`, `data/`, `eb_data/` and the web build and snapshot outputs, **When** `git status` is run, **Then** none of them appears as untracked or modified (ignore list per PLAN.md §23.1 Plan).
2. **Given** a `.env` at the repo root, **When** Claude Code creates a new worktree, **Then** the worktree contains a copy of `.env` (§0.5, `.worktreeinclude`).
3. **Given** the committed agent settings, **When** an agent tries to read `./.env` or `./.env.local` with its Read tool, **Then** the read is denied; **When** it reads `.env.example`, **Then** the read succeeds (§0.5).
4. **Given** a new teammate with only the runbook, **When** they follow it in order, **Then** every human step from §0.2 Track B through §0.5 appears in sequence, each ending with a check they can see (for example "check-env shows Object Storage READY"), and the laptop-only rule for `LINODE_TOKEN` and AWS keys and the after-event revocation list from §0.5 are included.

---

### Edge Cases

- `.env` is absent rather than empty: identical behavior to an empty file (every row MISSING or FAKE, build exits 0).
- A value is set to the example placeholder (for example `replace-me`): treated as not provided for probing, but a placeholder app-secret token or hash is malformed and fails the build phase (§0.4).
- A probe hangs or the network is down: the row is FAILED after the per-probe limit; the command never crashes and still prints the full matrix and exits by the phase rule.
- Credentials present and the fake mode also selected: the row reports FAKE, since the mode variable is what the running code honors.
- The readiness command runs on the VM, where `LINODE_TOKEN` and AWS keys must never be present (§0.5): those rows are MISSING or FAKE, and neither `integrate` nor `demo` requires them.
- The MCP probe before anything is deployed: "unauthenticated POST /mcp returns 401" can only be checked once a public URL exists; before that, the row reports on data folders and token length only, and the full probe is required only by the `demo` phase.
- The optional AWS row with `LLM_FALLBACK=none`: FAKE, never a failure in any phase (§0.4 "never required").
- A secret shorter than four characters, or a masked value: masking still never reveals more than the last four characters.
- Secret generation interrupted or run concurrently: an existing valid value is never replaced; a re-run only fills gaps.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The readiness command MUST evaluate exactly the integrations and probes listed in PLAN.md §0.4 and report one row per integration with a status of READY, FAKE, MISSING or FAILED and a human-readable next step.
- **FR-002**: The readiness command MUST support the three phases in §0.4, `build` (default), `integrate` and `demo`, and MUST exit 0 when the phase's gate is met and 1 otherwise, using exactly the per-phase requirements stated there.
- **FR-003**: In the `build` phase the command MUST fail only on malformed values (a token shorter than 32 characters, a placeholder or non-bcrypt dashboard hash); missing or faked integrations MUST NOT fail it.
- **FR-004**: The command MUST never print more than the last four characters of any secret, in any output format or error message (constitution VI).
- **FR-005**: The command MUST offer a machine-readable output alongside the human table so agents and scripts can consume it.
- **FR-006**: Every live probe MUST have a bounded time limit (8 seconds per PLAN.md §23.1), and a timed-out or erroring probe MUST yield FAILED for that row without stopping the others.
- **FR-007**: The command MUST NOT place a Twilio voice call unless the operator passes the explicit call-test option (§0.4).
- **FR-008**: The Twilio row MUST be READY only when the account is active and not a trial, the balance is at least $10, and the configured number can make voice calls (§0.4).
- **FR-009**: The app-secrets row MUST be READY only when `INTERNAL_TOKEN` and `MCP_TOKEN` are present with at least 32 characters and `DASH_PASS_HASH` is a bcrypt hash (§0.4).
- **FR-010**: For each integration with a mode variable (`AI_MODE`, `VOICE_MODE`, `STORAGE_MODE`, `LLM_FALLBACK`), the row MUST report FAKE when the fake value is selected, taking precedence over credential checks.
- **FR-011**: The committed example environment file MUST contain every variable in PLAN.md §7.1, with the fake or placeholder values and comments given there, and no others; its defaults MUST select every fake mode.
- **FR-012**: The secrets command MUST write `INTERNAL_TOKEN`, `MCP_TOKEN` and `DASH_PASS_HASH` into `.env`, creating the file if needed, and MUST NOT overwrite any variable that already holds a value.
- **FR-013**: Generated tokens MUST be at least 32 characters; the dashboard hash MUST be bcrypt and MUST be written single-quoted so `$` signs survive (§7.1); the plain dashboard password MUST be shown once and never stored.
- **FR-014**: The repository MUST ignore `.env`, `.env.local`, `data/`, `eb_data/`, the web dependency, build and snapshot directories, and the Claude worktrees directory (§23.1 Plan; §6).
- **FR-015**: The repository MUST declare `.env` for copying into new Claude Code worktrees (§0.5).
- **FR-016**: The committed agent settings MUST deny the Read tool on `./.env` and `./.env.local` exactly as given in §0.5 and MUST leave `.env.example` readable.
- **FR-017**: A setup runbook MUST exist that orders the human steps of PLAN.md §0.2 (Track B), §0.3, §0.4 and §0.5, states which values stay on laptops only, and lists the after-event revocations.
- **FR-018**: Unit tests MUST cover masking, the phase logic with faked probe responses, and an empty `.env` passing the build phase with exit 0 (§17.1); none may touch the network (constitution VIII).
- **FR-019**: A single entry point (the Makefile targets named in §6 and §23.1: `secrets`, `check-env` with `PHASE`, `test`, `dev`, `fixtures`, `deploy`) MUST expose these commands so builders and agents invoke them the same way.

### Key Entities

- **Integration row**: one §0.4 integration; attributes: name, the env vars it reads (§7.1), the probe performed, resulting status (READY, FAKE, MISSING, FAILED), masked evidence, next step.
- **Phase**: `build`, `integrate` or `demo`; defines which rows must be READY and which malformed values fail, exactly as in §0.4.
- **Readiness report**: the ordered set of rows for one run plus the phase and overall pass or fail; rendered as a table and as machine-readable output.
- **Mode variable**: `AI_MODE`, `VOICE_MODE`, `STORAGE_MODE`, `LLM_FALLBACK` (and `EB_DATA_DIR` pointing at the public release); the switch that selects a fake mode and makes a row FAKE.
- **App secret**: `INTERNAL_TOKEN`, `MCP_TOKEN`, `DASH_USER`/`DASH_PASS_HASH`; generated locally, with length and format rules from §0.4 and quoting rules from §7.1.
- **Env file set**: `.env.example` (committed, fake values), `.env` and `.env.local` (gitignored, agent-unreadable, worktree-copied).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a laptop with an empty or absent `.env`, the readiness command finishes in the default phase with exit 0 and 100% of rows MISSING or FAKE (PLAN.md §23.1 "Done when").
- **SC-002**: Across every output of the readiness and secrets commands, including machine-readable output and errors, zero occurrences of more than the last four characters of any secret; verified by an automated test.
- **SC-003**: The full test suite passes with zero credentials and the network disabled, including the three cases in the §17.1 `test_check_env.py` row.
- **SC-004**: No single probe exceeds 8 seconds, so a run with every integration unreachable still completes and prints the full matrix.
- **SC-005**: Any number of readiness runs without the call-test option produce zero outbound voice calls on the Twilio account.
- **SC-006**: Running the secrets command twice in a row leaves `.env` unchanged on the second run; after the first run the tokens are 32+ characters and the app-secrets row is READY.
- **SC-007**: After filling in a real value for an integration, the next run shows that row READY with no code change (§23.1 Notes); the `integrate` gate can therefore pass by about 4 PM as targeted in §0.6.
- **SC-008**: In a fresh clone with `.env` present, git reports zero env files as untracked, a new Claude Code worktree contains `.env`, and an agent Read of `.env` is denied while `.env.example` succeeds.
- **SC-009**: A teammate can go from a fresh clone to a build-phase pass using only the runbook, with every §0.2 Track B human step present in the same order as PLAN.md.

## Dependencies & Scope

- **Owner**: Builder B (PLAN.md §0.1, §6, §23.1), in the spec 001 session started at about T+20 (§0.2).
- **Depends on**: nothing. This is the first spec to run; specs 002 to 009 depend on it.
- **PLAN.md sections covered**: §0.4 (readiness matrix, probes, phases, fake modes), §0.5 (secrets handling, worktree include, agent deny rules), §0.6 (what proceeds without keys), §7.1 (the variable list, copied never redesigned, constitution I), the `test_check_env.py` row of §17.1, and the Builder B files in §6 that belong to spec 001.
- **Out of scope**: creating any cloud resource (VM, firewall, DNS name, bucket, certificate) and deploying, which is spec 002; the fake code paths inside each integration (rules fallbacks, simulated voice, local evidence storage, Enterprise-Bench adapter), which the owning specs build against the mode variables fixed here (§0.6); `CLAUDE.md`, owned by Builder A, which carries the "never cat `.env`" instruction (§0.5).

## Assumptions

- The four statuses in the feature description are the complete set; the optional AWS row with `LLM_FALLBACK=none` reports FAKE (what §0.2 informally calls "SKIPPED").
- The example environment values in §7.1 are the fake values; copying the example unchanged is a valid zero-credential configuration once the app secrets are generated, and `.env.example` itself never holds a real value.
- Probes are live network checks, so a readiness run outside tests may use the network; the automated tests fake every probe response.
- `LINODE_TOKEN` and the AWS keys are laptop-only (§0.5); the `integrate` and `demo` gates never require them, so the VM passes those phases without them.
- The readiness command reads the same `.env` the application reads, with the single-quote convention from §7.1, so the hash it validates is the one the dashboard login will use.
- After-event cleanup (revoke the Linode token and Object Storage key, rotate the Twilio auth token, delete the MCP token, §0.5) is documented in the runbook, not automated.
