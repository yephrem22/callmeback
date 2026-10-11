# Research: UI Live Integration (spec 007)

No NEEDS CLARIFICATION remained after surveying the merged code (eb607fc): `web/src/lib/api.ts`, the spec 004 feature folders, `web/scripts/snap.mjs`, `app/main.py`, `app/api.py` and PLAN.md §14.5, §14.9, §14.10, §19.

## R1. Polling cadences (FR-001)

- **Decision**: `refetchInterval` on the hooks in `lib/api.ts`, live mode only (`isFixtures` → `false`): invoices 2 000 ms; the open invoice `(q) => terminal(q.state.data?.status) ? 5 000 : 1 000`, where terminal is RELEASED, HELD or FAILED; health 15 000 ms. Tab data (stats, payments, vendors, audit, change cases) polls every 2 000 ms only while its tab is mounted (TanStack stops polling unmounted queries). `refetchIntervalInBackground: false`; the existing `retry: 1` stays. On an error TanStack keeps the last good data, and no toast fires for query errors (edge case "backend briefly unreachable").
- **Rationale**: exactly §14.9. Polling only the open tab keeps the request rate near 2 req/s for the stage laptop.
- **Alternatives**: SSE or WebSocket push (rejected: spec Assumptions "no push channel"); one global interval (rejected: §14.9 cadences differ per query).

## R2. Selection in live mode (FR-002, edge "reset while selected")

- **Decision**: the live selection stays local state in `Layout`. Loading a sample selects the new id (already wired through `QueueList` → `onSelect`). Reset clears it: the Demo controls reset calls a `onReset` callback that clears the selection. A selected invoice that returns 404 (removed by a reset from another browser) also clears the selection.
- **Rationale**: the URL is the fixture scenario's state in fixtures mode; live ids are ephemeral and need not be bookmarkable.

## R3. Errors after user actions (FR-028, edge 409)

- **Decision**: `useAction` gets a default `onError` that shows `toast.error(title, { description })` from `lib/errors.ts`. 409: "That action isn't available for this invoice any more." plus "The case was updated; check the current status and try again." 404: "That invoice no longer exists." plus "It was probably cleared by a demo reset." 400: the API's `detail`. Network failure: "Couldn't reach the server." plus "Check the connection; the dashboard keeps retrying." Every error invalidates the queries so the next poll corrects a stale view.
- **Rationale**: §14.6 copy rule (say what happened and what to do next). Mutations are user actions, so their toasts respect FR-019.

## R4. Simulate in Demo controls (FR-017, §19.2 backup plan)

- **Decision**: Demo controls show, for the selected invoice when `actions.can_simulate`, "Vendor says yes" (using the tab's last-four input) and "Vendor says no". With no selection or no `can_simulate`, the tab explains "Select a case that is calling, or a retryable hold, to simulate the vendor's answer." The case-level Simulate chips from spec 004 stay as they are.
- **Rationale**: §19.2 says "open Demo controls → Simulate 'no'"; the last-four input already exists in the tab but was not wired.

## R5. DevRev cases tab (FR-016)

- **Decision**: add `getChangeCases()`, `getChangeCase(id)` and hooks. The list shows account name, requested change, status (word + icon), sender and created time; selecting a row shows the excerpt, signals, the callback status, and the verification timeline and final label with "sandbox: routed to the team demo line" (PLAN.md §15). Fixtures mode returns `[]` (no change-case fixtures exist) and keeps the current empty copy.
- **Rationale**: `/api/change-cases` exists (spec 005); spec 008 creates the cases. The tab must show them on stage (§19.1 2:35).

## R6. SIMULATED badge (FR-007, edge)

- **Decision**: `CallbackPanel` shows a review-tone outline badge "SIMULATED" with an icon next to the "Callback" heading when `verification.source === "simulated"`, reusing the gallery candidate's styling. Never shown for `twilio`.

## R7. Audit export (FR-015, P1)

- **Decision**: an "Export JSON" link in the audit header downloads the entries already returned (a client-side Blob of `{entries, chain_ok, broken_at}` named `audit-<subject or all>-<date>.json`). No new endpoint (spec Assumptions).

## R8. Health error state (edge)

- **Decision**: when `useHealth()` errors, every dot shows the held tone with the word "unreachable" and the tooltip "Couldn't reach /api/health (<message>). The queue and case keep updating on their own." The AI chip reads "AI: unknown".

## R9. 12-hour call times (spec 005 T037 note)

- **Decision**: every UI time goes through `lib/format.ts::formatChicago`, whose `"time"` style is now 12-hour Chicago time (it was `hour12: false`), so the call time reads `h:mm AM/PM`, e.g. "Held. The vendor said no on the 8:46 PM call." `app/ledger.py::_chicago_hhmm` returns the same 12-hour form in Chicago time, so the red-team reason matches.
- **Rationale**: the rest of the UI uses 12-hour times ("Fri 4:52 PM"); PLAN.md's "10:42" example is format-neutral.

## R10. SPA fallback (FR-024)

- **Decision**: `app/main.py` mounts `SpaStaticFiles(directory=web/dist, html=True)` last: a `StaticFiles` subclass whose 404 for a GET returns `index.html`, except for paths under `api/`, `twilio/`, `internal/`, `mcp` and `healthz`, which keep their real 404. A `mount_web(app, dist)` helper makes it testable with a temporary dist.
- **Rationale**: routers are matched before the mount, so API routes win; unknown client paths load the app shell. Caddy keeps basic auth in front (spec 002).

## R11. Fixtures contract (FR-026, SC-003)

- **Decision**: extend `tests/test_fixtures_contract.py` to: (a) validate every `web/src/fixtures/<scenario>/*.json` with the InvoiceDetail shape checker from `tests/test_invoice_detail_shape.py` (exact top-level keys, nested key sets, masking); (b) run `scripts/export_fixtures.py` into a temporary directory and assert its files have the same key paths as the committed fixtures; (c) keep the existing live-API ⊇ fixture check.
- **Rationale**: (a) and (b) catch fixture drift; (c) catches API drift. No network.

## R12. The live story run (FR-027, SC-001, SC-002, SC-004)

- **Decision**: `snap.mjs --live --api http://localhost:8000` runs §19.1 against a running backend (simulated voice, AI off, DEMO_MODE=1).
  - **Setup**: reset, then pre-run Heartland through the API: from-sample, then simulate yes with 4455.
  - **The story, driven through the UI**: open the dashboard (empty case); load "Acme: normal" from the Load-a-sample menu → PAID; load "Acme: urgent bank change" → CALLING; Demo controls → Vendor says no → HELD; "Try to make the AI pay" → dialog and trace; Audit tab; Vendors tab; DevRev tab; header.
  - **Captures**: one screenshot per step at 1024×576 (1280×720 at 125%), in light, then the whole run in dark.
  - **Fails on**: any console error, any non-localhost request, or a stamp that takes more than 1.5 s to change after the API reports the new status (1 s poll + render).
- **Prototype comparison**: the existing fixtures run (`snap.mjs`) is regenerated, and the live screenshots are reviewed against the matching fixture steps; differences are recorded in `docs/design/decisions.md`.

## R13. ACH batch download (US4, P3)

- **Decision**: out of this spec's P1/P2 work. The control stays absent because no export endpoint exists, which satisfies US4 AC1's "absent rather than broken".
