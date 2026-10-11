# Design research note (spec 004, FR-001; 15-minute pass, 2026-10-10)

## Personas and their top decisions (PLAN.md §14.1)

| Persona | Context | Top decisions the screen must support |
|---|---|---|
| **AP specialist** (primary) | Works a queue of a few hundred invoices a week at a mid-size company; under time pressure; not technical | Can I pay this now? If not, why not, and what happens next? Which invoices need me at all? |
| **Controller** | Approves exceptions, owns vendor-master changes, answers to auditors and the bank | Why was this held or released? Was the bank change verified, by whom, when? Can I export the evidence? |
| **Judges on a projector** | Three minutes, about 5 m away, judging as everyday web users | Green paid, red held, phone ringing, AI blocked, all without explanation |

Reading order follows PLAN.md §14.2: decision first and largest, then the reasons and the destination change, then the live callback, then the evidence, with AI output secondary and clearly labelled.

## What the guidance says about this fraud

- Vendor-impersonation and business email compromise remain the most common payments-fraud vector in AFP's annual Payments Fraud and Control survey; the control every source recommends is an out-of-band callback to a **previously known** number before changing payment details. We render that rule on screen: "number on file, not the one in the email".
- The FBI IC3 report puts annual BEC losses in the billions; the Google/Facebook case ($120M+) is the canonical story and opens the pitch (PLAN.md §19.1).
- Nacha's 2026 risk-management rule asks ACH originators to monitor for false-pretenses fraud. The hash-chained audit log is framed as that evidence (PLAN.md §13.2).

## Patterns to borrow (PLAN.md §14.4) and where they come from

| Pattern | Seen in | Here |
|---|---|---|
| Triage list beside a detail pane with j/k | Linear, Superhuman, Front | Queue + case |
| A risk score explained by weighted factors | Stripe Radar | Risk breakdown |
| "On file vs new" comparison for changed payment details | bill-pay vendor bank-change alerts (Bill, Melio, Tipalti) | Destination card |
| A step list with live status icons | GitHub checks, Vercel deploy logs | Callback stepper |
| A span waterfall for agent and tool calls | LangSmith, Langfuse, Jaeger | Agent trace |
| An audit trail with an integrity indicator | GitHub audit log, compliance tools | Audit tab |
| The "PAID" rubber stamp | paper accounts payable | Decision stamp |

Observations that shaped the candidates:

- Radar-style factor lists work because each factor is a sentence a human can repeat; our flag `detail` strings are written that way ("acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')").
- Bank-change alerts in bill-pay tools put old and new account side by side in monospace; the eye compares the last four digits, so we mask everything else and keep routing numbers in full.
- Check-style step lists read at distance because each step has a word and an icon, never a color alone; same for our stepper and status chips.
- Trace waterfalls are for the AWS judges, not the AP specialist, so they open on demand in a sheet.

## Sources consulted

- AFP Payments Fraud and Control Survey (annual; BEC/vendor impersonation prevalence; callback as control) — https://www.afponline.org/
- FBI Internet Crime Complaint Center, Internet Crime Report (BEC losses) — https://www.ic3.gov/
- Nacha, Risk Management Framework and the 2026 fraud-monitoring rule — https://www.nacha.org/
- Stripe Radar risk insights (score with contributing factors) — https://docs.stripe.com/radar
- shadcn/ui Vite installation, dark mode and chart docs — https://ui.shadcn.com/docs/installation/vite, https://ui.shadcn.com/docs/dark-mode/vite, https://ui.shadcn.com/docs/components/chart
- Linear, Superhuman and Front product pages (triage layouts); GitHub checks UI; LangSmith and Langfuse trace views.

Time box respected: this note was produced alongside the candidate build; it is a checklist for the gate, not a literature review.
