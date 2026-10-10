# Contract: design tokens (PLAN.md §14.6 → CSS variables)

Names are shadcn's where they exist, plus four status tokens and one AI token. Declared in `web/src/index.css` on `:root` (light) and `.dark`.

## Light ("security paper")

| Token | CSS variable(s) | Hex | Use |
|---|---|---|---|
| paper | `--background`, `--card`, `--popover` | `#F5F7F6` | page and surfaces |
| ink | `--foreground`, `--card-foreground` | `#17242E` | text |
| rule | `--border`, `--input` | `#D3DCD9` | borders, dividers |
| ledger | `--primary`, `--ring` | `#0B6B61` | actions, links, focus ring |
| paid | `--paid` | `#1E7A46` | released |
| review | `--review` | `#9A5B00` | needs review, calling |
| held | `--held`, `--destructive` | `#B42318` | held, denied, blocked |
| ai | `--ai` | `#4C4FB8` | anything an AI wrote |
| muted | `--muted` / `--muted-foreground` | `#E9EEEC` / `#4B5B64` | quiet surfaces, secondary text |
| chart | `--chart-1..5` | ledger, paid, review, held, ai | charts use status colors only |

All text colors above pass 4.5:1 on paper (PLAN.md §14.6).

## Dark ("ink navy")

| Token | Hex | Note |
|---|---|---|
| `--background` | `#0F1B22` | not pure black |
| `--card`, `--popover` | `#15242D` | surface |
| `--foreground` | `#E3EBEE` | text |
| `--border`, `--input` | `#2A3B45` | |
| `--primary`, `--ring` | `#4FB3A6` | ledger, lightened |
| `--paid` | `#4CC38A` | ≥ 4.5:1 on background |
| `--review` | `#E0A94A` | ≥ 4.5:1 |
| `--held`, `--destructive` | `#F0776B` | ≥ 4.5:1 |
| `--ai` | `#9A9CF0` | ≥ 4.5:1 |
| `--muted` / `--muted-foreground` | `#1C2E38` / `#A9B8C0` | |

Dark values are verified with a contrast check in Phase 4 and corrected there if any fails; corrections are recorded in `docs/design/decisions.md`.

## Typography

- Sans: IBM Plex Sans 400/500/600; `font-variant-numeric: tabular-nums` on amounts and counts.
- Mono: IBM Plex Mono 400/500 for routing numbers, account numbers and audit hashes only.
- Scale: 14, 16, 18, 22, 28, 40 px; base 16 px. Sentence case everywhere except the stamp.

## Motion

- `.stamp-in`: `transform: scale(1.15) → 1` over 180 ms, once, on reaching a decided status.
- `@media (prefers-reduced-motion: reduce)`: no animation anywhere.

## Status rendering rule

Every status is rendered as **word + icon + color**: `CheckCircle2` paid, `PhoneCall` calling, `Hourglass` review, `OctagonX` held, `Sparkles` AI (lucide names). Color alone is never the only signal.
