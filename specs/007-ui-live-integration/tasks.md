---

description: "Task list for spec 007: UI Live Integration"
---

# Tasks: UI Live Integration

**Input**: Design documents from `specs/007-ui-live-integration/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Prerequisites**: specs 004 (prototype, fixtures, `snap.mjs`), 005 (the §7.6 API) and 006 (voice) merged at eb607fc.

**Tests**: Python tests come first where behavior is deterministic (`tests/test_ledger_wording.py`, `tests/test_spa_fallback.py`, the extended `tests/test_fixtures_contract.py`). The web has no unit-test framework, so web tasks are verified by `npm run typecheck && npm run lint && npm run build` after each phase and by the Phase 4 `snap.mjs --live` story run. That run fails on any console error, any non-localhost request, or a stamp that changes more than 1.5 s after the API.

**Organization**: phases follow plan.md "Phases". Each task carries the user story it serves.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 the case comes alive on the real API · US2 the 3-minute story on the projector · US3 secondary surfaces polished · US4 ACH batch (P3)

## Path Conventions

`web/src/` for the dashboard, `app/` and `tests/` for Python, `web/scripts/` for Playwright. No redesign: keep spec 004's components, tokens and copy. No §7 contract changes. Never edit `app/schema.sql`, `app/models.py` or `app/state.py`.

---

## Phase 1: Live data layer

**Purpose**: the queue, the open case and the header stay current on their own (PLAN.md §14.9). Refused actions say what happened. Call times read as 12-hour.

**Independent Test**: `pytest tests/test_ledger_wording.py`; `npm run typecheck && npm run lint && npm run build`; then, with uvicorn plus `VITE_API_MODE=live npx vite`, loading "Acme: urgent bank change" selects it and shows CALLING without a reload.

- [x] T001 [P] [US1] Create `tests/test_ledger_wording.py`: with a HELD(DENIED_BY_VENDOR) invoice whose verification `updated_at` is `2026-10-11T01:46:00Z`, `ledger.can_release(...)[1]` reads "invoice is HELD (vendor denied the change on the 8:46 PM call)" (Chicago, 12-hour, research R9); a CONFIRMED verification's reason reads "vendor confirmed by … on the 8:46 PM call"; the bank-change history note uses the same form. The test must fail before T002.
- [x] T002 [US1] Edit `app/ledger.py::_chicago_hhmm` to return `"%-I:%M %p"`-style 12-hour Chicago time (portable: strip a leading zero with `lstrip("0")`), keeping "unknown time" for missing input. Keep the function name and callers; run `tests/test_ledger.py` and `tests/test_redteam.py` unchanged.
- [x] T003 [P] [US1] Make `web/src/lib/format.ts::formatChicago` "time" style 12-hour (drop `hour12: false`; `decide.ts::lastEventTime` already uses it), so the held sentence reads "Held. The vendor said no on the 8:46 PM call." (research R9).
- [x] T004 [US1] Edit `web/src/lib/api.ts`:
  - live-only `refetchInterval` per data-model.md "Polling": invoices `2000`; the open invoice `(q) => ["RELEASED","HELD","FAILED"].includes(q.state.data?.status ?? "") ? 5000 : 1000`; health `15000`; stats, payments, vendors and audit `2000`; `refetchIntervalInBackground: false`; fixtures mode gets `false`.
  - Add `getChangeCases()`, `getChangeCase(id)`, `useChangeCases()` and `useChangeCase(id)` (`GET /api/change-cases[/{id}]`, 2 s, `[]` in fixtures mode).
  - Give `useAction` a default `onError` that calls `toast.error(title, { description })` from `lib/errors.ts` and then invalidates every query.
- [x] T005 [P] [US1] Create `web/src/lib/errors.ts`: `describeError(e: unknown) -> { title, description }` per contracts/ui-data.md "Error copy". 409 gives "That action isn't available for this invoice any more." / "The case was updated; check the current status and try again." 404 gives "That invoice no longer exists." / "It was probably cleared by a demo reset. Pick another case." 400 gives "The request was refused." / the API detail. Network errors and 5xx give "Couldn't reach the server." / "Check the connection; the dashboard keeps retrying." Parse the status from the `"<status>: <detail>"` message thrown by `http()`.
- [x] T006 [P] [US1] Add the `ChangeCase` type to `web/src/lib/types.ts` exactly as data-model.md: `requested_change` is `"billing_contact" | "payment_details" | "remit_address" | "admin_contact" | "other"`; `status` is `"OPEN" | "CALLING" | "CONFIRMED" | "DENIED" | "UNCLEAR" | "NO_ANSWER" | "CLOSED"`; `request_excerpt` is "≤ 500 chars"; `verification` is `{id, source, step, phone_masked, events, final_label} | null`.
- [x] T007 [US1] Edit `web/src/features/shell/Layout.tsx` and `web/src/features/shell/Tabs.tsx` for live selection:
  - Clear the selection when Reset demo succeeds (pass an `onReset` callback from `Layout` through `BottomTabs` to `DemoTab`).
  - Clear it when the selected invoice's query fails with 404.
  - Keep "Load a sample" selecting the new id, which is already wired in `QueueList`.
  - Fixtures mode is unchanged.
- [x] T008 [P] [US1] Edit `web/src/features/shell/Header.tsx` for the health error state (research R8): when `useHealth()` has `isError`, every dot shows the held tone with the word "unreachable" and the tooltip "Couldn't reach /api/health (<message>). The queue and case keep updating on their own."; the AI chip reads "AI: unknown".

**Checkpoint**: `pytest -q`, then web typecheck, lint and build; commit "spec 007 phase 1"; stop and report.

---

## Phase 2: Live surfaces

**Purpose**: the live panels and tabs PLAN.md §14.9 lists that the prototype only showed with fixtures.

**Independent Test**: with the live dev setup, the fraud case → Demo controls → Vendor says no shows HELD with a SIMULATED badge; the red-team dialog names the layer and the trace opens; the DevRev tab lists a case created through `/internal` or a test insert; the audit export downloads JSON.

- [x] T009 [P] [US1] Edit `web/src/features/callback/CallbackPanel.tsx`: when `verification.source === "simulated"`, show a "SIMULATED" badge (review-tone outline, `FlaskConical` icon, uppercase, the gallery candidate's styling) next to the "Callback" heading. Never show it for `twilio` (FR-007).
- [x] T010 [US2] Edit `web/src/features/shell/Tabs.tsx` `DemoTab` (FR-017, §19.2 backup plan):
  - Accept the selected `InvoiceDetail | null`.
  - When `actions.can_simulate`, show "Vendor says yes" (using the tab's last-four input; digits only, 4 max) and "Vendor says no" for that invoice, with the toasts "Simulated: vendor said yes/no".
  - Otherwise show "Select a case that is calling, or a retryable hold, to simulate the vendor's answer."
  - Pass `detail` from `Layout` through `BottomTabs`.
- [x] T011 [P] [US3] Create `web/src/features/devrev/ChangeCases.tsx` and use it for the DevRev tab in `web/src/features/shell/Tabs.tsx` (FR-016, research R5):
  - **List** from `useChangeCases()`: account name, requested change in words, status as a word plus icon, sender, created time.
  - **Detail** for the selected row (the first by default) from `useChangeCase(id)`: request excerpt, signals as short labels, the callback timeline and final label, a SIMULATED badge when `verification.source === "simulated"`, and the note "sandbox: routed to the team demo line".
  - **Empty list**: keep the existing copy.
- [x] T012 [P] [US2] Edit `web/src/features/evidence/AuditList.tsx`: add an "Export JSON" link to the chain header that downloads `{entries, chain_ok, broken_at}` as `audit-<subject or "all">-<YYYY-MM-DD>.json` through a Blob URL (FR-015, research R7). Keep "Chain verified" only when `chain_ok`; otherwise name `broken_at`.
- [x] T013 [US3] Verify against live data and fix within spec 004's design:
  - The red-team dialog states the layer ("the Strands payment-guard plugin" / "the ledger's own policy check" / "the agent refused") and the API reason.
  - The trace sheet opens automatically (`onRedteam` → `setQuery({ trace: 1 })`), and a `guard_block` row renders in the held color.
  - The Payments tab shows the KPI strip and the ledger with masked destinations and the ACH effective date.
  - The Vendors tab shows Heartland's bank-change history marked "verified by callback".

  Record any fix in the phase commit.

**Checkpoint**: web typecheck, lint and build; `pytest -q`; commit "spec 007 phase 2"; stop and report.

---

## Phase 3: Serving and contract

**Purpose**: the built dashboard is served correctly by FastAPI (FR-024), and fixtures cannot drift from the API (FR-026).

**Independent Test**: `pytest tests/test_spa_fallback.py tests/test_fixtures_contract.py`.

- [x] T014 [P] [US2] Create `tests/test_spa_fallback.py` using `app.main.mount_web(app, dist)` on a fresh `FastAPI()` with a temporary dist containing `index.html` and `assets/app.js`:
  - `/` and `/assets/app.js` return their files.
  - `/some/client/path` returns `index.html` with 200.
  - `/api/nope`, `/twilio/nope`, `/internal/nope`, `/mcp/x` and `/healthz/x` keep 404.
  - A POST to an unknown path is not the shell.
  - With no `index.html`, `mount_web` mounts nothing.

  It must fail before T015.
- [x] T015 [US2] Edit `app/main.py`: add `SpaStaticFiles(StaticFiles)`, whose `get_response` returns `index.html` for a GET that would 404, unless the path starts with `api/`, `twilio/`, `internal/`, `mcp` or `healthz`. Add `mount_web(app, dist)`, which mounts it at `/` only when `dist/index.html` exists. Call it last, in place of the current mount (contracts/serving.md).
- [x] T016 [US2] Extend `tests/test_fixtures_contract.py` (research R11):
  - Validate every `web/src/fixtures/<scenario>/*.json` with `tests.test_invoice_detail_shape._check_shape`: exact top-level keys, nested key sets, masking.
  - Run `scripts/export_fixtures.py` into `tmp_path` (the same way `test_export_fixtures_writes_all_scenarios` does) and assert every exported file has the same key paths as the committed fixture of the same name.
  - Keep the existing live-API ⊇ fixture tests.

**Checkpoint**: `pytest -q`; commit "spec 007 phase 3"; stop and report.

---

## Phase 4: Story run and snapshots

**Purpose**: prove the PLAN.md §19.1 story end to end on the live API at projector size, and compare it with the prototype (FR-027, SC-001, SC-002, SC-004, SC-005).

**Independent Test**: `node web/scripts/snap.mjs --live --base http://localhost:5173 --api http://localhost:8000` exits 0.

- [ ] T017 [US2] Edit `web/scripts/snap.mjs`: add `--live` with `--api <url>` (research R12).
  - **Setup through the API**: `POST /api/demo/reset {}`; pre-run Heartland (from-sample `03_heartland_bank_change`, then simulate yes with 4455; wait for RELEASED).
  - **The story through the UI** at 1024×576 (1280×720 at 125%), for each theme:
    - empty case;
    - Load a sample → "Acme: normal" → wait for the PAID stamp;
    - Load a sample → "Acme: urgent bank change" → wait for CALLING;
    - open Demo controls → Vendor says no → wait for HELD;
    - Try to make the AI pay → wait for the dialog, then close it;
    - the Audit log tab, the Vendors tab, the DevRev cases tab;
    - the header.
  - **Screenshots**: `live-<nn>-<step>-<theme>.png`, one per step.
  - **Latency**: measure from the API status change (poll `GET /api/invoices/{id}` in the script) to the stamp text change in the DOM, and fail if any exceeds 1500 ms.
  - **Hygiene**: keep the existing console-error and third-party-host checks.
  - **No credentials**: send no basic-auth header unless `--user`/`--pass` are given (for the VM run).
- [ ] T018 [US2] Run the live story locally (uvicorn with `AI_MODE=off VOICE_MODE=simulated DEMO_MODE=1` on a fresh seeded DB, plus `VITE_API_MODE=live npx vite`) in light and dark mode. Fix any console error, foreign request, latency breach or §14.10 issue (legibility at 1024×576, contrast, status word + icon), within spec 004's design.
- [ ] T019 [US3] Regenerate the fixtures snapshot set (`node web/scripts/snap.mjs` against `vite` in fixtures mode) and review it side by side with the live set. Record differences, and whether each is expected (live data) or a regression, in `docs/design/decisions.md` under "Spec 007 live vs prototype". Fix regressions.

**Checkpoint**: web checks, `pytest -q`; commit "spec 007 phase 4"; stop and report.

---

## Phase 5: Hand-off

- [ ] T020 [US2] Deploy to the VM: git bundle → `git pull --ff-only` in `/opt/callmeback`; `docker compose up -d --build app`; confirm `/` serves the built dashboard behind basic auth and `/some/path` serves the shell.
- [ ] T021 [US2] On the VM, with the presenter's browser and the real phone: Reset demo, pre-run Heartland (press 1, then 4455), then run the §19.1 story with a real "no". Confirm every step, and the simulated-no backup. Record the timings and issues in `docs/decisions.md`.
- [ ] T022 [P] Run `specs/007-ui-live-integration/quickstart.md` §1–§4 locally and fix anything that does not match.
- [ ] T023 Run `/speckit-converge` until it reports converged, then rebase on `origin/main`, run `pytest -q` and the web checks, push, and fast-forward `main`. Remove the worktree when asked.

---

## Dependencies & Execution Order

- **Phase 1**: T001 before T002. T003, T005, T006 and T008 can run in parallel. T004 depends on T005 and T006. T007 depends on T004.
- **Phase 2** depends on Phase 1 (hooks and types). T009, T011 and T012 can run in parallel. T010 and T013 come after T007.
- **Phase 3** is independent of Phase 2. T014 before T015. T016 is independent.
- **Phase 4** depends on Phases 1–3.
- **Phase 5** depends on Phase 4.
- **US4** (ACH batch, P3) has no task. The control stays absent because no export exists, which satisfies US4 AC1's "absent rather than broken" (research R13).

## Parallel Example: Phase 1

```text
T001 tests/test_ledger_wording.py     T003 web/src/lib/decide.ts
T005 web/src/lib/errors.ts            T006 web/src/lib/types.ts       T008 Header.tsx
```

## Implementation Strategy

- **MVP (US1, milestone A7 "dashboard runs on the live API")**: Phases 1–2.
- **Stage-ready (US2)**: Phases 3–4 plus T020/T021, the 7 PM checkpoint rehearsal.
- **US3** polish rides along in Phase 2 (T011, T013) and Phase 4 (T019, dark mode).
- One phase at a time. After each: checks, commit, stop and report.

## Notes

- Never advance a status locally (FR-003). Every state comes from a poll.
- Toasts only after user actions (FR-019). Query errors never toast.
- Fixtures mode must still make zero `/api` requests (the `--live` flag is the only way the snapshot script talks to the API).
