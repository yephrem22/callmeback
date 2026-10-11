# Tasks: UI Design Prototype

**Input**: Design documents from `specs/004-ui-design-prototype/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: No unit-test framework in this spec. Every phase is gated by `npm run typecheck && npm run lint && npm run build` and, from Phase 2 on, by the snapshot script plus a recorded self-critique (FR-018). The spec's acceptance scenarios are checked by eye against the snapshots.

**Organization**: Phases follow plan.md: 1 scaffold and tokens, 2 research note and gallery (**hard stop** for the human gate U2), the human gate (no code), 3 prototype P1, 4 P2 polish, 5 hand-off. Story mapping: Phase 2 → US1, gate → US2, Phase 3 → US3, Phase 4 → US4 and US5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an unfinished task)
- **[Story]**: US1–US5 from spec.md; setup and cross-cutting tasks carry no label
- Paths are repository-relative. This spec writes only under `web/` (except `web/src/fixtures/`, which is read-only here) and `docs/design/`.

## Path Conventions

Single Vite app in `web/` per plan.md; features by panel under `web/src/features/`; shadcn-owned components under `web/src/components/ui/`.

---

## Phase 1: Scaffold and tokens (U1 part 1)

**Purpose**: a building, type-checked shell with the §14.6 tokens, both themes, routing, the fixture-backed API client and the display helpers everything else uses.

- [x] T001 Scaffold `web/` with `npm create vite@latest web -- --template react-ts` (run from the repo root with Node 22 on PATH), `cd web && npm install`, then `npm install tailwindcss @tailwindcss/vite` and `npm install -D @types/node`. Set `src/index.css` to `@import "tailwindcss";`, add `"baseUrl": "."` and `"paths": {"@/*": ["./src/*"]}` to `tsconfig.json` and `tsconfig.app.json`, and set `vite.config.ts` to `plugins: [react(), tailwindcss()]`, `resolve.alias["@"] = ./src`, `server.proxy["/api"] = "http://localhost:8000"`. Add `"typecheck": "tsc -b --noEmit"` to `package.json` scripts (lint and build come from the template).
- [x] T002 Initialise shadcn in `web/`: `npx shadcn@latest init -t vite -b radix --css-variables -y` (fall back to interactive defaults if a flag is rejected; record the working command here), then `npx shadcn@latest add -y button card badge table tabs dialog sheet tooltip separator skeleton sonner scroll-area dropdown-menu alert progress chart collapsible input label switch resizable`. Commit `components.json` and `src/components/ui/*` as generated.
- [x] T003 [P] Install runtime deps in `web/`: `npm install @tanstack/react-query lucide-react sonner recharts @fontsource/ibm-plex-sans @fontsource/ibm-plex-mono` and dev deps `npm install -D @playwright/test && npx playwright install chromium`. Create `web/.env.development` with `VITE_API_MODE=fixtures` and `web/.env.production` with `VITE_API_MODE=live`.
- [x] T004 [P] Write `web/src/index.css`: `@import "tailwindcss"`, font imports are in `main.tsx`; `:root` and `.dark` blocks with every variable in `contracts/design-tokens.md` (paper `#F5F7F6`, ink `#17242E`, rule `#D3DCD9`, ledger `#0B6B61`, paid `#1E7A46`, review `#9A5B00`, held `#B42318`, ai `#4C4FB8`; dark background `#0F1B22`, surface `#15242D`, text `#E3EBEE`, lightened status colors), `--chart-1..5`, Tailwind `@theme inline` mappings so `bg-paid`, `text-held`, `text-ai` etc. exist, base font 16 px IBM Plex Sans, `.tabular` (`font-variant-numeric: tabular-nums`), `.mono` (IBM Plex Mono), `.stamp-in` keyframe (scale 1.15 → 1, 180 ms, once) and `@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important } }`, visible focus ring `outline: 2px solid var(--ring)` on `:focus-visible`.
- [x] T005 [P] Write `web/src/lib/types.ts` mirroring PLAN.md §7.6 exactly as spec 003 emits it (see `specs/003-core-engine/contracts/http-api.md` and `tests/test_invoice_detail_shape.py` key sets): `InvoiceDetail` with `id, status, hold_reason, source, created_at, invoice_number, amount_cents, decided_at, email{...}, extracted{fields{name:{value,source,mismatch}}, phone_numbers_in_email, llm_status}, vendor{id,name,domains,phone_masked,bank_masked,history[],median_cents}|null, risk{points,tier,action,sender_status,amount_ratio,lookalike{sender_domain,known_domain,diff[]}|null,flags[{code,points,title,detail,evidence}],bank_changed,policy_version}|null, destination{on_file|null,requested|null,changed}, analyst{status,report|null}, verification{id,source,step,phone_masked,events[],first_answer|null,last4_ok,final_label,attempts}|null, payment{...}|null, memo|null, trace[], audit[{seq,ts,actor,event,summary,hash_short}], actions{can_review,can_retry_call,can_simulate,can_redteam}, ai_fallback`; plus `InvoiceListRow`, `Health`, `Stats`, `PaymentsView`, `VendorView`, `AuditView`, `ScenarioIndex`, `ScenarioName`, `Status`, `HoldReason`, `Tier`, `Action`. Enable `resolveJsonModule`.
- [x] T006 [P] Write `web/src/lib/fixtures.ts` (`FixtureStore`): typed imports of `src/fixtures/index.json`, every scenario step file (via `import.meta.glob("../fixtures/*/*.json", { eager: true })`), and the six list/tab files; state `currentStep: Record<ScenarioName, number>` and `selected: ScenarioName | "none"`; methods `listRows()` (one `InvoiceListRow` per scenario at its current step, newest first), `detail(id)`, `advance(scenario)`, `setStep(scenario, n)`, `select(scenario)`, `health()`, `stats()`, `payments()`, `vendors()`, `audit()`; a tiny subscribe/notify so React re-renders (`useSyncExternalStore`).
- [x] T007 Write `web/src/lib/api.ts` per research R4 and `contracts/fixtures-and-routes.md`: `const MODE = import.meta.env.VITE_API_MODE ?? "fixtures"`; functions `getInvoices, getInvoice, getHealth, getStats, getPayments, getVendors, getAudit, postReview, postRetryCallback, postRedteam, postSimulate, postReset, postAiMode, postFromSample, postUpload`; fixtures mode routes to `FixtureStore` (mutations advance the matching scenario or no-op); live mode uses `fetch("/api/...")` with JSON and throws on non-2xx. Export TanStack Query hooks `useInvoices`, `useInvoice(id)`, `useHealth`, `useStats`, `usePayments`, `useVendors`, `useAudit` with no `refetchInterval` yet (spec 007 adds it).
- [x] T008 [P] Write `web/src/lib/route.ts`: `useRoute()` parsing `location.pathname` (`/` or `/gallery`) and `?scenario&step&theme&tab&trace`, `setQuery(partial)` using `history.replaceState` plus a `popstate` listener; `isDev = import.meta.env.DEV`.
- [x] T009 [P] Write `web/src/lib/format.ts` and `web/src/lib/decide.ts`: `formatCents(cents)` → `$48,750.00`; `formatChicago(iso, style: "time" | "datetime" | "date")` via `Intl.DateTimeFormat` with `timeZone: "America/Chicago"`; `maskedCheckLine(routing, account_masked)`; `stampFor(status, hold_reason)` → `"PAID" | "HELD" | "REVIEW" | "CALLING" | null` (RELEASED→PAID, HELD→HELD, NEEDS_REVIEW→REVIEW, CALL_PENDING|CALLING|VERIFYING→CALLING, else null); `decisionSentence(detail)` producing exactly the PLAN.md §14.9 sentences: "Paid. ACH effective Oct 12.", "Waiting for the vendor to answer.", "Held. The vendor said no on the 10:42 call." (time = last verification event in Chicago), "Needs review: the amount is 2.1 times usual.", "Held. No vendor record, so there's no trusted number to call.", plus sensible variants for the other hold reasons and for SCORED/AUTO_APPROVED/REVIEW_APPROVED/CONFIRMED ("Approved; releasing.", "Confirmed by the vendor; releasing."); `flagTone(flag)` → `"weighted" | "note"`; `statusIcon(status)` → lucide icon component per `contracts/design-tokens.md`.
- [x] T010 Write `web/src/lib/theme.tsx` (shadcn Vite pattern: `ThemeProvider` with `defaultTheme="light"`, `storageKey="cmb-theme"`, system via `matchMedia`, `?theme=` override from `useRoute`) and `web/src/main.tsx` (fontsource imports for Plex Sans 400/500/600 and Plex Mono 400/500, `QueryClientProvider`, `ThemeProvider`, `<Toaster/>` from sonner, `<App/>`). Write `web/src/App.tsx` as the route switch: `/` → `features/shell/Layout`; `/gallery` → `isDev ? lazy(() => import("./features/gallery/Gallery")) : NotFound`. Set `document.body.dataset.ready = "true"` after first render of the requested state.
- [x] T011 Write `web/src/features/shell/Header.tsx` and `Layout.tsx`: title "Call Me Back"; health dots (db, model, twilio, storage) from `useHealth` with tooltips and a word label each; "Running on {deploy_label}" and inference latency; theme dropdown (light/dark/system); "AI: live" / "AI: off (rules only)" chip. Layout = header, a two-column body (queue 280 px, case flexible) and a bottom tab bar (Payments, Vendors, Audit log, DevRev cases, Demo controls, and a "Show agent trace" button on the right) with placeholder panels. Empty case area reads "Load a sample invoice to start."

**Checkpoint (phase 1)**: `npm run typecheck && npm run lint && npm run build` pass; `npm run dev` shows the header, empty queue and empty-state copy in both themes with no console errors. Commit. Stop and report.

---

## Phase 2: Research note and gallery (U1 part 2) → HARD STOP

**Goal**: the research note and all fourteen candidates with two variants each, on real fixtures, at `/gallery` in dev only; the snapshot script exists so this and every later phase can self-review.

**Independent Test**: `/gallery` shows 14 numbered cards each with shows/serves/fields/components, two rendered variants and a copyable snippet; the production build contains no gallery chunk; `node scripts/snap.mjs --gallery` writes gallery screenshots in both themes.

- [x] T012 [P] [US1] Write `docs/design/research.md` (15-minute pass, FR-001): the three personas from PLAN.md §14.1 with their top decisions; the patterns to borrow from §14.4 with where they come from; what AP/BEC guidance says about callbacks to a known number; how Stripe Radar, bill-pay vendor-change alerts, GitHub checks and span waterfalls present risk and progress; a sources list with links (AFP Payments Fraud survey, FBI IC3 report, Nacha 2026 rule page, Stripe Radar docs, product pages). ≤ 80 lines.
- [x] T013 [P] [US1] Write `web/scripts/snap.mjs` per research R9: args `--base` (default `http://localhost:5173`), `--gallery`, `--out` (default `web/snapshots`); reads `web/src/fixtures/index.json`; for each scenario step × theme opens `/?scenario=&step=&theme=`, viewport 1024×576, waits for `body[data-ready="true"]`, screenshots to `<scenario>-<nn>-<theme>.png`; `--gallery` opens `/gallery?theme=` and takes a full-page shot per theme; collects `console.error` and every request URL, exits 1 if any error or any non-localhost host; prints a summary. Add `"snap": "node scripts/snap.mjs"` to `package.json`; add `web/snapshots/` to `.gitignore` (already there via spec 001).
- [x] T014 [US1] Write the gallery frame: `web/src/features/gallery/Gallery.tsx` (page with a numbered index, light/dark note, each card via `CandidateCard`), `CandidateCard.tsx` (title "#n Name", "What it shows", "Serves", "§7.6 fields" as code chips, "Components", two variants side by side with labels A and B, a snippet `<pre>` with a Copy button via `navigator.clipboard`), and `candidates.tsx` exporting `CANDIDATES: Candidate[]` (type from data-model.md). Candidates render against the fixture step named in each task below, fetched from `FixtureStore`.
- [x] T015 [P] [US1] Candidate 1 Risk breakdown bar in `web/src/features/case/RiskBreakdown.tsx`: one horizontal stacked bar of `risk.flags[].points` (weighted flags only) with tier lines at 20 and 50 and direct labels; variant A shadcn `chart` (Recharts stacked bar), variant B plain CSS flex bar with inline labels; 0-point flags listed under it as notes with an info icon. Reads `risk.flags`, `risk.points`, `risk.tier`. Fixture: acme_fraud step 1.
- [x] T016 [P] [US1] Candidate 2 Risk meter in `web/src/features/case/RiskMeter.tsx`: a single bar with green/amber/red bands (0–20–50–max(points,100)) and a marker at `risk.points`, the number "160 risk points" beside it; variant A horizontal, variant B compact pill for the queue. Reads `risk.points`, `risk.tier`. Fixture: acme_fraud step 1.
- [x] T017 [P] [US1] Candidate 3 Amount vs history in `web/src/features/case/AmountVsHistory.tsx`: strip plot of `vendor.history[].amount_cents` with a median line at `vendor.median_cents` and this invoice (`amount_cents`) highlighted and labelled "4.1× usual"; variant A Recharts scatter via shadcn `chart`, variant B SVG dots on a line; omitted when `vendor.history` is empty. Reads `vendor.history`, `vendor.median_cents`, `amount_cents`, `risk.amount_ratio`. Fixtures: acme_fraud step 1 and prairie_review step 1.
- [x] T018 [P] [US1] Candidate 4 Lookalike diff in `web/src/features/case/LookalikeDiff.tsx`: the two domains aligned character by character in Plex Mono with the swapped characters from `risk.lookalike.diff` highlighted in the held color and a caption "'1' in place of 'l'"; variant A stacked lines, variant B inline with an arrow-free "imitates" label. Reads `risk.lookalike`. Fixture: acme_fraud step 1.
- [x] T019 [P] [US1] Candidate 5 Destination card in `web/src/features/case/DestinationCard.tsx` with `CheckLine.tsx`: "on file" and "requested" rows as check lines (bank name, routing in full with an inline SVG transit symbol, `account_masked`), changed parts highlighted in the held color when `destination.changed`; variant A two rows, variant B side-by-side columns; `requested` null → one row. Reads `destination`. Fixtures: acme_fraud step 1, acme_normal step 1.
- [x] T020 [P] [US1] Candidate 6 Callback stepper in `web/src/features/callback/CallbackStepper.tsx`: steps Dialing, Ringing, Answered, Asked, Answer, Verdict from `verification.events` with live-status icons (check, spinner, dot) and the header "Callback to the number on file •••-•••-0199, not the one in the email"; SIMULATED badge when `verification.source === "simulated"`; variant A horizontal, variant B vertical timeline with timestamps. Reads `verification.events`, `verification.phone_masked`, `verification.source`, `verification.step`. Fixtures: acme_fraud steps 2 and 3.
- [x] T021 [P] [US1] Candidate 7 Transcript bubble in `web/src/features/callback/TranscriptBubble.tsx`: the spoken or keyed answer from `verification.first_answer` as a quote bubble with chips "classifier: NO" and "verifier: DENIED" (verifier chip in the AI color), confidence shown as a word+number; `last4_ok` result line; variant A bubble, variant B table row. Reads `verification.first_answer`, `verification.last4_ok`, `verification.final_label`. Fixtures: acme_fraud step 3, heartland step 3.
- [x] T022 [P] [US1] Candidate 8 Agent trace waterfall in `web/src/features/trace/TraceWaterfall.tsx`: spans per `trace[]` row grouped by agent with `duration_ms` bars, `guard_block` rows in the held color and labelled BLOCKED; variant A waterfall, variant B grouped list; fixtures have empty traces, so the gallery renders a documented sample built from the §7.6 trace example plus an "no agent runs yet" empty state. Reads `trace[]`.
- [x] T023 [P] [US1] Candidate 9 Audit chain list in `web/src/features/evidence/AuditList.tsx`: rows `seq, time (Chicago), actor, event, summary, hash_short` in Plex Mono with a "Chain verified ✓ (N entries)" seal; variant A dense table, variant B timeline with hash links; broken chain state shows "Chain broken at #n". Reads `audit[]`, and `AuditView.chain_ok/broken_at` for the tab. Fixture: acme_fraud step 3 and `audit.json`.
- [x] T024 [P] [US1] Candidate 10 KPI strip in `web/src/features/payments/KpiStrip.tsx`: money released, money held, calls placed, median time to decision from `Stats`, tabular numerals, each with a word label and icon; variant A four tiles, variant B one line. Reads `stats.json`.
- [x] T025 [P] [US1] Candidate 11 Payments ledger table in `web/src/features/payments/LedgerTable.tsx`: `payments[]` with amount, destination (`bank_name`, routing, `account_masked`), method, effective date, released by; held summary below; variant A shadcn table, variant B card list. Reads `payments.json`.
- [x] T026 [P] [US1] Candidate 12 Decision stamp variants in `web/src/features/case/Stamp.tsx`: PAID, HELD, REVIEW, CALLING as outlined, −6° rotated stamps in their status colors with the icon, `.stamp-in` entrance once, reduced-motion safe; variant A outlined, variant B filled label; plus the one-sentence decision from `decisionSentence`. Reads `status`, `hold_reason`, `verification`, `payment`, `risk.amount_ratio`. Fixtures: one step per stamp.
- [x] T027 [P] [US1] Candidate 13 Queue rows in `web/src/features/queue/QueueRow.tsx`: vendor name, `amount_display`, status word+icon, tier chip, age (Chicago relative), selected state, focus ring; variant A two-line row, variant B single line with a right-aligned status. Reads `InvoiceListRow`. Fixture: `invoices_list.json`.
- [x] T028 [P] [US1] Candidate 14 Vendor change history in `web/src/features/vendors/BankHistory.tsx`: before and after check lines marked "verified by callback, HH:MM" with the invoice id, from `VendorView.bank_history`; variant A card per change, variant B table. Reads `vendors.json`. Fixture: `vendors.json` (Heartland has one change).
- [x] T029 [US1] Register all fourteen in `candidates.tsx` with `fields` listing the exact §7.6 keys each reads and a `snippet` string showing the JSX call; apply the chart rules (direct labels, no legend where avoidable, status colors from CSS variables, tabular numerals, no pie/3D, nothing tooltip-only); confirm the production build has no gallery chunk (`grep -ril gallery web/dist/assets` is empty).
- [x] T030 [US1] Run `npm run typecheck && npm run lint && npm run build`, start `npm run dev`, run `node scripts/snap.mjs --gallery`, review the two gallery screenshots, write the top three issues under "Self-critique: gallery" in `docs/design/decisions.md`, fix them, re-run. Commit.

**HARD STOP (milestone U2)**: report what was built and how it was checked. Do not start Phase 3 until `docs/design/decisions.md` has a winner for every slot.

---

## Human gate (U2): both builders pick the winners (US2) — no code

- [ ] T031 [US2] The team reviews `/gallery` for 15 minutes and fills the table in `docs/design/decisions.md`: for each slot of PLAN.md §14.3 (decision, risk, destination, callback, evidence, queue, trace, tabs) the winning candidate number, the winning variant (A or B) and a one-line reason; plus a "Contract requests" list (empty if none). Losing candidates stay in the gallery.

---

## Phase 3: Prototype P1 (U3) — the demo story on fixtures (US3)

**Goal**: the §14.3 layout assembled from the winners, a dev-only scenario player, URL-addressable steps, and all five scenarios playing end to end with the §14.9 copy.

**Independent Test**: `/?scenario=<each>&step=<each>` renders; the player steps through all five; snapshots for 14 steps × 2 themes pass the script.

- [ ] T032 [US3] Build `web/src/features/case/CaseView.tsx` in the §14.2 order: `CaseHeader` (vendor name, invoice number, amount, received time), the winning `Stamp` with `decisionSentence`; "Why: N risk points" with the winning risk component and each flag as `+points Title` with detail and evidence (0-point flags as notes); the winning `DestinationCard`; the `LookalikeDiff` when `risk.lookalike` is set; `AmountVsHistory` when `vendor.history` is non-empty.
- [ ] T033 [US3] Build `web/src/features/callback/CallbackPanel.tsx`: the winning stepper, `TranscriptBubble`, last-four result, SIMULATED badge; hidden when `verification` is null (unknown vendor) and shown with a "Waiting for the vendor to answer." state for CALL_PENDING.
- [ ] T034 [US3] Build `web/src/features/evidence/EvidenceTabs.tsx` with shadcn `tabs`: Email (`EmailView.tsx`: headers and body in a scroll area, reply-to highlighted when different), Extracted fields (`ExtractedFields.tsx`: table with chips "text and AI agree" / "text" / "AI" / "AI disagreed; text used" from `source`+`mismatch`), Audit trail (winning `AuditList`), Analyst note (`AnalystNote.tsx`: AI color, label "AI-written explanation; doesn't change the decision", "Rules fallback" chip when `analyst.status === "fallback"`, "Pending" state when `report` is null).
- [ ] T035 [US3] Build `web/src/features/trace/TraceSheet.tsx` (shadcn `sheet`, right side) hosting the winning trace component, opened by the "Show agent trace" button and by `?trace=1`; empty state "No agent runs yet" for fixtures.
- [ ] T036 [US3] Build `web/src/features/case/Actions.tsx` from `actions`: "Approve payment" and "Reject" (`can_review`), "Call vendor again" (`can_retry_call`), "Try to make the AI pay" with a held-color outline (`can_redteam`), Simulate yes/no (`can_simulate`, only when `health.demo_mode`); in fixtures mode each advances the scenario via `api.ts` and shows a sonner toast with the §14.9 wording ("Payment approved", "Calling the vendor again"); no arrows, sentence case.
- [ ] T037 [US3] Build `web/src/features/case/PaymentCard.tsx` (amount, destination masked, method ACH-CCD, effective date, released by) shown when `payment` is set.
- [ ] T038 [US3] Build `web/src/features/queue/QueueList.tsx` using the winning `QueueRow`: "Load a sample ▾" dropdown listing `samples/manifest.json` titles (in fixtures mode it selects the scenario) and an "Upload .eml" button (disabled in fixtures mode with a tooltip), rows from `useInvoices`, selection bound to `?scenario=`.
- [ ] T039 [US3] Build `web/src/features/demo/ScenarioPlayer.tsx` (dev only, floating bottom-right): scenario select, step back/forward, "play all" at 1.5 s per step, current step label; writes `?scenario&step` so the URL always reflects the state; also exposes `window.__cmb.setStep(scenario, n)` for the snapshot script.
- [ ] T040 [US3] Wire everything in `Layout.tsx`: selected scenario → `useInvoice(id)` → `CaseView`, `CallbackPanel`, `EvidenceTabs`, `Actions`, `PaymentCard`; empty state; `document.body.dataset.ready/scenario/step` after render; `?tab=` opens a bottom tab.
- [ ] T041 [US3] Verify every acceptance scenario of US3 by stepping through all five scenarios: acme_normal PAID with payment card and no flags; acme_fraud 160 points, lookalike diff, changed destination, CALLING with the stepper, transcript "No, we never changed banks" with classifier/verifier chips, HELD "Held. The vendor said no on the HH:MM call.", red-team action present; heartland confirmed with last-four passed and PAID, vendors tab shows "verified by callback"; prairie REVIEW "Needs review: the amount is 2.1 times usual." with Approve/Reject then PAID; unknown vendor HELD with the no-vendor sentence, no callback panel, no review/retry. Fix anything that doesn't match PLAN.md §14.9.
- [ ] T042 [US3] Run the checks, `node scripts/snap.mjs` (28 images), review at 1024×576 for the §14.10 bar (stamp, sentence and points visible without scrolling; nothing scrolls horizontally; body ≥ 16 px), write the top three issues under "Self-critique: prototype P1" in `docs/design/decisions.md`, fix, re-run. Commit.

**Checkpoint (phase 3)**: all five scenarios play from fixtures with the §14.9 copy; snapshots clean. Stop and report (milestone U3).

---

## Phase 4: P2 polish — themes (US4) and keyboard (US5), plus the tabs

- [ ] T043 [P] [US4] Dark-theme contrast pass: compute contrast for every status color, `--foreground`, `--muted-foreground` and chart colors against `--background` and `--card` in `.dark` (a small Node script `web/scripts/contrast.mjs` using WCAG relative luminance); adjust values in `index.css` until text ≥ 4.5:1 and icons ≥ 3:1; record the final hexes in `docs/design/decisions.md` and `contracts/design-tokens.md`.
- [ ] T044 [P] [US4] Verify theme persistence (`localStorage["cmb-theme"]`), light default on first visit, `?theme=` override, and that every status still shows word + icon in dark mode across all 14 steps (snapshots `-dark.png`).
- [ ] T045 [P] [US5] Keyboard navigation in `QueueList.tsx`: roving `tabIndex`, `j`/`k` move the highlighted row, `Enter` opens it (sets `?scenario=`), `ArrowDown`/`ArrowUp` as aliases, focus ring in the ledger color visible on rows and every button/tab; no global shortcut fires while typing in an input.
- [ ] T046 [P] [US4] Fill the bottom tabs on fixtures: Payments (`KpiStrip` + `LedgerTable` + held summary), Vendors (`VendorTable.tsx` + winning `BankHistory`), Audit log (`AuditList` on `audit.json` with the chain seal), DevRev cases (`features/devrev/CasesTable.tsx`, empty state "No change cases yet"), Demo controls (`features/demo/DemoControls.tsx`: Reset demo with a confirmation dialog, AI live/off switch, Simulate yes/no with a last-four input; all wired to `api.ts`, which no-ops or advances in fixtures mode).
- [ ] T047 [US4] Reduced-motion check: with `prefers-reduced-motion: reduce` emulated in the snapshot script (`page.emulateMedia`), the stamp renders without animation; add a `--reduced-motion` flag to `snap.mjs` and one extra pair of screenshots.
- [ ] T048 Run the checks and the full snapshot set in both themes; confirm SC-005 to SC-010 (console clean, no third-party hosts, keyboard pass, zero non-§7.6 keys in fixtures, build green); write "Self-critique: P2" in `docs/design/decisions.md`, fix the top three, re-run. Commit.

**Checkpoint (phase 4)**: dark mode verified, keyboard pass done, tabs populated. Stop and report.

---

## Phase 5: Hand-off

- [ ] T049 [P] Write `web/README.md` (≤ 60 lines): scripts, `VITE_API_MODE`, fixtures mode and the scenario player, URL parameters, the snapshot script, the gallery route, and the hand-off notes for spec 007 (where polling goes, which components read which `actions`).
- [ ] T050 [P] Confirm `make test` runs the web checks now that `web/package.json` exists, and that `Dockerfile`'s web stage (`npm ci && npm run build`) succeeds with the committed `package-lock.json`.
- [ ] T051 Rebase on `origin/main`, run `make test`, push, fast-forward `main`, remove the worktree (PLAN.md §0.8 step 6).

---

## Dependencies & Execution Order

- **Phase 1**: T001 → T002 → (T003, T004, T005, T006, T008, T009 in parallel) → T007 (needs T005, T006) → T010 (needs T004, T008) → T011 (needs T007, T010).
- **Phase 2**: T012 and T013 any time; T014 after Phase 1; T015–T028 in parallel after T014 (each its own file, each reading named fixtures); T029 after all candidates; T030 last. **Hard stop.**
- **Gate**: T031 by humans.
- **Phase 3**: T032–T039 mostly parallel after the gate (each a separate file); T040 after all of them; T041, T042 last.
- **Phase 4**: T043–T047 parallel; T048 last.
- **Phase 5**: after Phase 4.

### Story mapping

- US1 (P1): T012–T030. US2 (P1): T031. US3 (P1): T032–T042. US4 (P2): T043, T044, T046, T047. US5 (P2): T045.

### Parallel opportunities

- Phase 1: six foundation files at once after shadcn init.
- Phase 2: the fourteen candidates are fourteen independent files; the research note and the snapshot script run alongside.
- Phase 3: eight panel files in parallel before wiring.

## Implementation Strategy

1. Phase 1 fast: a building shell with tokens and the fixture client (under an hour).
2. Phase 2 is the MVP for this spec: the gallery is what the team reviews. Stop there.
3. After the gate, Phase 3 delivers the stage visuals; Phase 4 the quality bar; Phase 5 hands to spec 007.
4. After every phase: checks, snapshots, top-three fixes, commit, stop and report.

## Notes

- Fixtures under `web/src/fixtures/` are spec 003's output; never edit them here. Data gaps go to "Contract requests" in `docs/design/decisions.md`.
- `src/components/ui/` is shadcn-generated; edit only for theming.
- Node 22 must be on PATH: `export PATH="$HOME/.nvm/versions/node/v22.23.3/bin:$PATH"`.
- `.specify/feature.json` is machine-local; never commit it.
