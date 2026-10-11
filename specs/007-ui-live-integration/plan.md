# Implementation Plan: UI Live Integration

**Branch**: `worktree-ui-live-integration` (spec directory `specs/007-ui-live-integration`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification and the Plan prompt in PLAN.md §23.7.

## Summary

Wire the approved spec 004 prototype to the live spec 005/006 API and make it stage-ready, without redesigning anything. The API client already speaks every §7.6 route in live mode (`web/.env.production` sets `VITE_API_MODE=live`; Vite proxies `/api` in dev). This spec adds:
- the PLAN.md §14.9 polling cadences;
- live selection and reset behavior;
- user-facing errors for refused actions;
- the missing live surfaces: the SIMULATED badge, Simulate with the last four in Demo controls, the DevRev cases tab, the audit export, and the health error state;
- 12-hour call times;
- an SPA fallback when FastAPI serves `web/dist`;
- a fixtures contract test that validates every fixture file and the exporter;
- a `--live` mode for `snap.mjs` that runs the §19.1 story against the real API at 1280×720 / 125% and checks console errors, third-party requests and the one-second update budget.

## Technical Context

**Language/Version**: TypeScript 5 / React 19 (web), Python 3.12 (serving and contract test)

**Primary Dependencies**: Vite, Tailwind v4, shadcn/ui, TanStack Query v5 (`refetchInterval`), sonner, lucide-react, Playwright (snapshots and story run); FastAPI `StaticFiles`. No new dependencies.

**Storage**: none new; the UI reads the §7.6 API only.

**Testing**: `npm run typecheck && npm run lint && npm run build`; pytest for serving (`tests/test_spa_fallback.py`) and the fixtures contract (`tests/test_fixtures_contract.py`); `node web/scripts/snap.mjs --live` for the end-to-end story against a running API (simulated voice, AI off), and the existing fixtures run for the prototype comparison.

**Target Platform**: the presenter's laptop browser at 1280×720 and 125% zoom (a 1024×576 CSS viewport); the Chicago VM serving the built dashboard behind Caddy basic auth.

**Project Type**: the existing web app (`web/`) and the single Python package.

**Performance Goals**: every pipeline step visible within 1 s of landing (SC-001): the case polls every 1 s until it is terminal, then every 5 s; the queue polls every 2 s; health every 15 s.

**Constraints**: no redesign (spec 004's decisions are fixed); no §7 contract changes; fixtures mode keeps working with no `/api` requests; status never shown by color alone; contrast ≥ 4.5:1; zero console errors; zero third-party requests; toasts only after user actions.

**Scale/Scope**: about 12 web files touched and 1 new web feature folder (`features/devrev/`); 2 Python files (`app/main.py`, `app/ledger.py`); 2 test files; 1 script mode.

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. PLAN.md source of truth | §14.9 cadences, copy and actions rules applied as written; §7.6 shapes consumed unchanged | PASS |
| II. AI explains, code holds keys | the UI never advances a status (FR-003); actions follow server `actions` flags only | PASS |
| III. Fail closed | refused actions (409) show what happened and refresh; a stale view never offers an action the server would refuse | PASS |
| IV. Number on file | the callback panel states "number on file (vendor master), not from the email" from live data | PASS |
| V. Never blocked by setup | fixtures mode unchanged; the story run uses simulated voice and AI off | PASS |
| VI. Secrets stay in .env | no secrets in the web bundle; the snapshot script takes the dashboard password only as an argument for the VM run | PASS |
| VII. Evidence everywhere | audit chain header, `broken_at`, export link; SIMULATED badge | PASS |
| VIII. Test the deterministic | fixtures contract test, SPA fallback test, ledger wording test | PASS |
| IX. Designed for its users | §14.10 quality bar checked by the live story run in both themes | PASS |
| X. Small slices | five phases, each stops and reports | PASS |
| XI. Fresh code | all new | PASS |

Post-design re-check: no violations.

## Project Structure

```text
specs/007-ui-live-integration/
├── plan.md, research.md, data-model.md, quickstart.md, tasks.md
└── contracts/ ui-data.md (queries, cadences, mutations, copy), serving.md (SPA fallback)

web/src/
├── lib/api.ts              # refetchInterval per §14.9; change-case reads; mutation error handling
├── lib/types.ts            # ChangeCase types
├── lib/decide.ts           # 12-hour call times in the held sentence
├── lib/errors.ts           # status code → "what happened, what to do next" copy (new)
├── features/shell/Layout.tsx, Tabs.tsx, Header.tsx   # selection + reset; Demo controls simulate; health error state
├── features/callback/CallbackPanel.tsx               # SIMULATED badge
├── features/evidence/AuditList.tsx                   # export link
└── features/devrev/ChangeCases.tsx                   # DevRev cases list + detail (new)

web/scripts/snap.mjs        # --live: the §19.1 story against a running API
app/main.py                 # SPA fallback for web/dist (mounted last)
app/ledger.py               # 12-hour time in the blocked-release reason (matches the UI)
tests/test_spa_fallback.py, tests/test_fixtures_contract.py (extended)
```

**Structure Decision**: keep spec 004's feature-folder layout; add `features/devrev/` and `lib/errors.ts` only.

## Phases

1. **Live data layer**: polling cadences, live selection (load selects, reset clears, a vanished invoice clears), mutation errors with §14.6 copy, the health error state, change-case reads, 12-hour call times (UI and ledger).
2. **Live surfaces**: the SIMULATED badge, Simulate yes/no with the last four in Demo controls for the selected invoice, the DevRev cases tab (list + detail), the audit export link; check the red-team dialog and the trace auto-open against live data.
3. **Serving and contract**: SPA fallback in `app/main.py` with `tests/test_spa_fallback.py`; extend `tests/test_fixtures_contract.py` to validate every fixture file and the exporter output (FR-026).
4. **Story run and snapshots**: `snap.mjs --live` runs the §19.1 story (reset → Heartland pre-run → normal → fraud → simulated "no" → red team → Audit → Vendors → DevRev → header) at 1024×576 in light and dark, measuring status-to-screen latency, console errors and third-party hosts; regenerate the fixtures snapshots and compare with the live set; record the review.
5. **Hand-off**: deploy the built dashboard to the VM and run the story there with a real call; quickstart validation; `/speckit-converge`; merge.

## Complexity Tracking

No constitution violations to justify.
