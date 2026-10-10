# Call Me Back Constitution

Call Me Back is a 24-hour hackathon build (Hack Midwest 2026, team Tenex.ai) that stops
payments to fraudulent bank accounts. These principles govern every spec, plan, task and
commit in this repository.

## Core Principles

### I. PLAN.md Is the Source of Truth
Specs, plans and tasks MUST reference PLAN.md sections rather than restate or redesign them.
The contracts in PLAN.md §7 (environment variables, database schema, status machine, core
models, cross-workstream interfaces and the HTTP API) MUST be copied, never redesigned. When
anything conflicts with PLAN.md, PLAN.md wins. Changing §7 requires agreement from both
builders.

Rationale: two builders and many Claude Code sessions work in parallel; one frozen contract
is the only thing that lets their work meet.

### II. The AI Explains; the Code Holds the Keys
Scores, routing and release eligibility MUST be deterministic code. A model MAY make the
system more cautious, never less. Release MUST be enforced twice: once by a Strands plugin on
the release tool, and again inside the ledger. An agent may always hold a payment; only
verified code paths may release one.

Rationale: a model that can be talked into paying is the attack we exist to stop.

### III. Fail Closed
Errors, timeouts, unclear answers, no-answers and missing configuration MUST result in a
hold, a "not documented" answer, or a fake mode. They MUST never result in a release.

### IV. Call the Number on File
Verification calls MUST go to the vendor's phone number in the vendor master, never to a
number found in an email or a request. Any digits a model extracts MUST appear verbatim in
the source text or be discarded.

### V. Never Blocked by Setup
Every external integration (LLM inference, Twilio, Object Storage, DevRev and
Enterprise-Bench data, AWS) MUST have a fake or local mode selected by an environment
variable. The full test suite MUST pass with zero credentials.

Rationale: credentials arrive on the organizers' schedule, not ours; implementation must
never wait on them.

### VI. Secrets Stay in .env
Secrets MUST never be committed, printed, logged or pasted into specs, plans, prompts or
chat. Agents MUST NOT read, cat or print `.env`. Readiness is checked with `make check-env`,
which masks values to their last four characters.

### VII. Evidence Everywhere
Every decision MUST write an audit event, and every claim the system makes MUST cite its
source (a flag code, an audit entry, a source reference or a trace row).

### VIII. Test What Is Deterministic
Policy, extraction, the answer classifier, the state machine, the ledger and the audit chain
MUST have unit tests built from the PLAN.md test vectors (§8.4, §10, §12.4, §13, §17.1).
`make test` MUST pass before every commit. Nothing in pytest may call the network.

### IX. Designed for Its Users
The UI MUST use React, Tailwind CSS and shadcn/ui, follow PLAN.md §14, work in light and
dark mode, be legible from five metres on a 1280×720 projector at 125% zoom, and never rely
on color alone to convey status.

### X. Small Vertical Slices
Work MUST be implemented one phase at a time: implement a phase, stop, report what was
built, how it was tested and what was assumed, then commit. Scope order is P0, then P1,
then P2 as defined in PLAN.md §4. Spec Kit priority labels P1, P2 and P3 correspond to
PLAN.md P0, P1 and P2.

### XI. Fresh Code
Everything in this repository MUST be written after the hackathon kickoff (2026-10-10
09:30 America/Chicago). Libraries are allowed. Sponsor starter code MAY be adapted with
credit in the README.

## Technical Constraints

- Stack per PLAN.md §6: Python 3.12, FastAPI, SQLite (WAL), pydantic v2,
  `strands-agents[openai]==1.59.0`, Twilio 9.x; a separate MCP service on `mcp==1.30.0`;
  Vite, React, TypeScript, Tailwind CSS v4, shadcn/ui, Recharts, TanStack Query.
- Money is integer cents; time is UTC ISO-8601 in storage and America/Chicago on screen;
  account and phone numbers are masked to their last four digits everywhere outside the
  database, except that the Intake agent sees the raw email.
- Route handlers that touch SQLite, Strands or Twilio are plain `def`; only `/twilio/*`
  routes are `async def`, and they hand off to a thread pool after reading the form.
- Background work runs only in the two executors defined in PLAN.md §6, and a task never
  waits on a future from its own pool.
- Nothing in the dashboard loads from a CDN at runtime.

## Development Workflow

- Each spec runs in its own Claude Code worktree session, pinned with
  `SPECIFY_FEATURE_DIRECTORY`, in the order given in PLAN.md §0.8. Sessions edit only the
  files they own (PLAN.md §6) and ask before touching another session's files.
- Per spec: `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze` where PLAN.md §0.8 says
  to, then `/speckit-implement` one phase at a time, then `/speckit-converge`. Merge by
  rebasing on `main`, running `make test`, pushing and removing the worktree.
- `.specify/feature.json` is machine-local state and is never committed.
- Cut scope only in the order given in PLAN.md §4; the never-cut list there is absolute.

## Governance

This constitution supersedes all other practices in the repository. PLAN.md supersedes
specs, plans and tasks; where this constitution and PLAN.md appear to disagree, PLAN.md is
corrected or this constitution is amended, never silently ignored.

Amendments require agreement from both builders, a version bump per semantic versioning
(MAJOR for removed or redefined principles, MINOR for new principles or materially expanded
guidance, PATCH for clarifications), and a note in `docs/decisions.md`. Every plan and
every `/speckit-analyze` run checks compliance against these principles. Runtime guidance
for agents lives in `CLAUDE.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-10 | **Last Amended**: 2026-10-10
