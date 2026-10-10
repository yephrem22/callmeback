# Implementation Plan: UI Design Prototype

**Branch**: `worktree-ui-design` (spec directory `specs/004-ui-design-prototype`) | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-ui-design-prototype/spec.md` and the Plan prompt in PLAN.md §23.4.

## Summary

Design the Call Me Back dashboard before wiring it: a 15-minute research note, a development-only gallery of the fourteen PLAN.md §14.8 candidates (two variants each) rendered on the real fixtures spec 003 exported, a human gate where the team records winners, then a clickable prototype of the PLAN.md §14.3 layout with a development-only scenario player that steps through the five demo-story scenarios. Light and dark themes from the §14.6 tokens, j/k/Enter queue navigation, a Playwright snapshot script at the projector viewport, and zero runtime requests to third parties. Spec 007 later flips `VITE_API_MODE` to `live`.

## Technical Context

**Language/Version**: TypeScript 5 on Node 22 (`~/.nvm/versions/node/v22.23.3`), React 19, Vite 8

**Primary Dependencies**: `@tailwindcss/vite` + Tailwind CSS 4.3, shadcn/ui (CLI 4.21, radix base, CSS variables), Recharts 3.10 via shadcn `chart`, `@tanstack/react-query` 5, `lucide-react`, `sonner`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`, `@playwright/test` 1.64 (dev only, Chromium)

**Storage**: none. Fixtures in `web/src/fixtures/` (spec 003's exporter output); theme choice in `localStorage` under `cmb-theme`.

**Testing**: `npm run typecheck`, `npm run lint`, `npm run build` (all must pass per commit; `make test` runs them); `node scripts/snap.mjs` for visual self-review with console-error and third-party-request detection. No unit-test framework in this spec (constitution VIII covers the deterministic backend; the UI is validated by typecheck, build and snapshots).

**Target Platform**: evergreen desktop browsers; the stage target is Chrome on a 1280×720 projector at 125% zoom (effective 1024×576).

**Project Type**: single-page web app in `web/`, built to static files in `web/dist` that FastAPI serves (PLAN.md §14.5).

**Performance Goals**: first paint under 1 s on localhost; every scenario step renders without layout shift at 1024×576.

**Constraints**: fixtures mode makes no network requests; no CDN or third-party host at runtime; body text ≥ 16 px; text contrast ≥ 4.5:1, icons ≥ 3:1 in both themes; status never by color alone; `prefers-reduced-motion` honoured; the gallery and player are excluded from the production bundle; §7.6 shapes are read, never extended.

**Scale/Scope**: ~10 feature folders, 14 gallery candidates × 2 variants, 5 scenarios / 14 steps, 28 snapshots.

## Constitution Check

| Principle | Compliance | Status |
|---|---|---|
| I. PLAN.md source of truth | layout, tokens, copy and candidates come from §14; data shapes from §7.6 via spec 003's fixtures; no new fields | PASS |
| II. AI explains, code holds the keys | UI shows decisions; the analyst note is in the AI color and labelled "doesn't change the decision" | PASS |
| III. Fail closed | n/a to UI logic; missing data renders as omitted panels, never as invented values | PASS |
| IV. Number on file | callback panel says "number on file (vendor master), not from the email" | PASS |
| V. Never blocked by setup | fixtures mode needs nothing; no credentials | PASS |
| VI. Secrets in .env | the web app reads only `VITE_API_MODE` | PASS |
| VII. Evidence everywhere | audit list with chain indicator, trace sheet, source email all reachable | PASS |
| VIII. Test the deterministic | typecheck/lint/build gate each commit; backend vectors unaffected | PASS |
| IX. Designed for its users | React + Tailwind + shadcn, §14 followed, light/dark, projector legibility, word+icon status | PASS |
| X. Small vertical slices | phases below; hard stop at the human gate (U2) | PASS |
| XI. Fresh code | scaffolded after kickoff; libraries only | PASS |

Post-design re-check: no violations. Complexity Tracking stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-ui-design-prototype/
├── plan.md, research.md, data-model.md, quickstart.md
├── contracts/
│   ├── fixtures-and-routes.md   # fixture files, index.json, URL query params, dev-only routes
│   └── design-tokens.md         # §14.6 tokens → CSS variables, both themes
├── checklists/requirements.md
└── tasks.md                     # /speckit-tasks
```

### Source Code

```text
web/
├── package.json, vite.config.ts, tsconfig*.json, components.json, eslint.config.js
├── index.html
├── scripts/snap.mjs                      # Playwright snapshots (R9)
├── snapshots/                            # gitignored output
└── src/
    ├── main.tsx, App.tsx, index.css      # providers, route switch, tokens
    ├── components/ui/                    # shadcn-generated; theming edits only
    ├── lib/
    │   ├── types.ts                      # §7.6 shapes
    │   ├── api.ts                        # fixtures | live client (R4)
    │   ├── fixtures.ts                   # FixtureStore: index.json + typed JSON imports
    │   ├── route.ts                      # useRoute(): path + query (R3)
    │   ├── format.ts, decide.ts          # cents, Chicago time, stamp + decision sentence
    │   └── theme.tsx                     # ThemeProvider (R5)
    ├── features/
    │   ├── shell/        Header (health dots, deploy label, theme, AI mode), Layout, Tabs bar
    │   ├── queue/        QueueList, QueueRow, j/k/Enter
    │   ├── case/         CaseHeader, Stamp, DecisionLine, RiskBreakdown, RiskMeter, DestinationCard, CheckLine, LookalikeDiff, AmountVsHistory
    │   ├── callback/     CallbackStepper, TranscriptBubble, Last4Result, SimulatedBadge
    │   ├── evidence/     EmailView, ExtractedFields, AuditList, AnalystNote
    │   ├── trace/        TraceSheet, TraceWaterfall
    │   ├── payments/     KpiStrip, LedgerTable
    │   ├── vendors/      VendorTable, BankHistory
    │   ├── devrev/       CasesTable (fixture-empty)
    │   ├── demo/         DemoControls (disabled placeholders until spec 007), ScenarioPlayer (dev only)
    │   └── gallery/      Gallery page, candidates.tsx registry (14 × 2 variants), CandidateCard
    └── fixtures/                          # from spec 003 (read-only here)

docs/design/
├── research.md                            # FR-001
└── decisions.md                           # the human gate's winners; self-critique log
```

**Structure Decision**: single Vite app, features by panel so each gallery candidate and each layout slot maps to one folder. `components/ui` is shadcn-owned. Fixtures stay where spec 003 writes them.

## Phases (each stops and reports; U2 is a hard stop)

1. **Phase 1, scaffold and tokens (U1 part 1)**: Vite + React + TS, Tailwind v4, shadcn init and component set from §14.5, fonts, tokens in `index.css` for both themes, `ThemeProvider`, `useRoute`, `types.ts`, `FixtureStore` and `api.ts` (fixtures mode), `format.ts`/`decide.ts`. Gate: typecheck, lint, build pass; an empty shell renders with the header.
2. **Phase 2, research note and gallery (U1 part 2)**: `docs/design/research.md`; the fourteen candidates with two variants each on fixture data; `/gallery` dev-only; chart rules applied; snapshot script with a `--gallery` flag. Gate: all candidates render; build excludes the gallery chunk. **Stop for the human gate.**
3. **Human gate (U2)**: both builders fill `docs/design/decisions.md`. No code.
4. **Phase 3, prototype P1 (U3)**: layout §14.3 using the winners, queue, case (stamp, decision, risk, destination, callback, evidence tabs), trace sheet, scenario player, URL-addressable steps, empty state. Gate: all five scenarios play; snapshots reviewed; top three issues fixed.
5. **Phase 4, P2 polish**: dark theme contrast pass, j/k/Enter, payments/vendors/devrev tabs on fixtures, reduced-motion check, final snapshots. Gate: SC-004 to SC-010.
6. **Phase 5, hand-off**: README notes for spec 007, converge, merge.

## Complexity Tracking

None.
