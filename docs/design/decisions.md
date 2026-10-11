# Design decisions (spec 004)

## The human gate (milestone U2): pick the winners

Open `http://localhost:5173/gallery` (dev server, light theme first, then dark). Spend 15 minutes together. For each slot, write the winning candidate number, the variant (A or B) and one line on why. The prototype (phase 3) uses only what is recorded here; losing candidates stay in the gallery.

Reviewed 2026-10-10 evening by the team (Yoseph with Sahaj and Shubhangi). Picks per candidate: 1B, 2A, 3A, 4A, 5B, 6B, 7B, 8B, 9B, 10A, 11A, 12A, 13A, 14A.

| Layout slot (PLAN.md §14.3) | Candidates to choose from | Winner | Variant | Reason |
|---|---|---|---|---|
| Decision (stamp + sentence) | 12 Decision stamp | 12 | A outlined | Reads as a rubber stamp; the filled variant competes with the status chips |
| Risk ("Why: N risk points") | 1 Risk breakdown bar, 2 Risk meter | 2 + 1 | 2A meter above, 1B CSS segments and list below | Meter gives the 5 m read; the CSS breakdown carries the detail without the chart library |
| Amount context | 3 Amount vs history | 3 | A Recharts strip | Axis ticks make the scale explicit (keeps Recharts in the bundle) |
| Lookalike callout | 4 Lookalike diff | 4 | A stacked | The two domains line up character for character |
| Destination | 5 Destination card | 5 | B two columns | On file vs requested side by side; the hot column is unmistakable |
| Callback progress | 6 Callback stepper | 6 | B vertical timeline | Timestamps and the asked question fit; never wraps |
| Callback answer | 7 Transcript bubble | 7 | B row | Compact under the timeline; chips stay readable |
| Evidence: audit | 9 Audit chain list | 9 | B timeline | Hash links show the chain visually |
| Agent trace sheet | 8 Agent trace waterfall | 8 | B grouped list | Groups per agent read better in a narrow sheet than bars |
| Queue | 13 Queue rows | 13 | A two lines | Amount and status both visible at 280 px |
| Payments tab | 10 KPI strip, 11 Payments ledger table | 10 + 11 | 10A tiles, 11A table | Finance-familiar table under four big numbers |
| Vendors tab | 14 Vendor change history | 14 | A cards | Before and after read as one event |

Rules of thumb while choosing: readable from 5 m at 1024×576; status always has a word and an icon; charts only where they add something a sentence cannot.

## Contract requests (fields the screen wanted that PLAN.md §7.6 lacks)

- none so far. (Everything the fourteen candidates render comes from the §7.6 payload as spec 003 emits it.)

## Self-critique: gallery (phase 2, 2026-10-10)

Reviewed `web/snapshots/gallery-*.png` and per-card captures at 1100 px. Top three issues and fixes:

1. **Horizontal callback stepper overflowed a half-width column** (six steps plus connectors), bleeding into the neighbouring variant. Fixed: the row now wraps and uses tighter connectors. Worth remembering for the prototype: at 1024 px the stepper has the full case width, so wrapping should not occur there.
2. **Amount-vs-history dots stacked on one spot** because the six past amounts sit within a few percent of the median. Fixed: small vertical jitter in both variants so each dot stays visible; the median line and the highlighted invoice are unaffected.
3. **Long code snippets clipped under the Copy button**. Fixed: snippets wrap.

Observations carried forward, no change made:

- The Recharts variants (1A, 3A) render fine but add ~140 kB gzipped to the bundle for the whole app; the CSS/SVG variants (1B, 3B) read at least as well at distance. If the gate picks the B variants everywhere, Recharts can be dropped from the production bundle.
- Audit summaries for `invoice_received`, `extraction_done` and `verification_final` repeat the event name; a richer one-line summary would come from the backend's `audit.list_entries` (spec 003/005), not the UI.
- All timestamps in fixtures read 10:00 because the exporter uses a fixed clock; the live API will show real times.
