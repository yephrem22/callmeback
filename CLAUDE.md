# Call Me Back: working agreement for Claude Code

- Read PLAN.md before working. It is the source of truth. The contracts in §7 are frozen, so ask before changing them.
- Work only on the active Spec Kit spec (SPECIFY_FEATURE_DIRECTORY) and follow the constitution in .specify/.
- Implement one phase at a time. After each phase, stop and report what you built, how you tested it, and what you assumed.
- Never read, cat, print or paste .env or any secret. Use `make check-env`, which masks values.
- Every integration has a fake mode (PLAN.md §0.4). Tests must pass with zero credentials.
- Run `make test` before every commit. Keep commits small, with clear messages.
- When unsure, fail closed: hold the payment, or say "not documented".
- Don't edit files another session owns (PLAN.md §6) without asking.
- Frontend: React, Tailwind and shadcn/ui only, following PLAN.md §14.
