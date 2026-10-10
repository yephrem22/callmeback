# Contract: Makefile targets and repository guardrails

Names are fixed by PLAN.md §6 and §23.1; this file states what each does so other specs and sessions can rely on them.

## Makefile

Variables: `PY ?= .venv/bin/python` (falls back to `python3` when `.venv/` is absent), `PHASE ?= build`, `ARGS ?=`, `DEPLOY_SSH ?= root@<HOST read from .env>`.

| target | runs | notes |
|---|---|---|
| `install` | `uv venv .venv` (if missing) then `uv pip install -p .venv/bin/python -r requirements.txt` | addition for the runbook; idempotent |
| `secrets` | `$(PY) scripts/gen_secrets.py $(ARGS)` | spec 001 |
| `check-env` | `$(PY) scripts/check_env.py --phase $(PHASE) $(ARGS)` | `make check-env PHASE=integrate`, `make check-env ARGS="--json"` |
| `test` | `$(PY) -m pytest -q`; then, only if `web/` exists: `cd web && npm run typecheck && npm run lint && npm run build` | PLAN.md §17.1 "Web checks"; fails fast on the first failing step |
| `dev` | `$(PY) -m uvicorn app.main:app --reload --port 8000` | `app/main.py` arrives with spec 005; until then prints "app/main.py not yet present (spec 005)" and exits 1 |
| `fixtures` | `$(PY) scripts/export_fixtures.py` | spec 003 (Builder A); prints a note and exits 1 if the script is absent |
| `deploy` | `ssh $(DEPLOY_SSH) 'cd /opt/callmeback && bash scripts/deploy.sh'` | spec 002 provides `scripts/deploy.sh`; exits 1 with a note if `HOST` is a placeholder |

All targets are `.PHONY`. The Makefile never `include`s `.env` and never echoes a value from it.

## `.env.example`

The content of PLAN.md §7.1 verbatim (see [env-example.md](env-example.md)). Defaults select every fake mode: `AI_MODE=off`, `VOICE_MODE=simulated`, `STORAGE_MODE=local`, `LLM_FALLBACK=none`, `TWILIO_VALIDATE_SIGNATURE=1`, `DEMO_MODE=1`. A test asserts the variable set equals §7.1's exactly.

## `.gitignore`

Keeps A's entries and adds (PLAN.md §23.1):

```
.env
.env.local
data/*
!data/.gitkeep
eb_data/
web/node_modules/
web/dist/
web/snapshots/
.claude/worktrees/
```

(`.specify/feature.json`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/` stay as A left them.)

## `.worktreeinclude`

```
.env
```

Claude Code copies the listed files into every worktree it creates (PLAN.md §0.5).

## `.claude/settings.json`

Exactly PLAN.md §0.5:

```json
{
  "permissions": {
    "deny": ["Read(./.env)", "Read(./.env.local)"]
  }
}
```

`.env.example` stays readable. The Spec Kit skills in `.claude/skills/` are unaffected.

## `docs/SETUP.md`

Ordered human runbook: tools (§0.3) → clone, `make install`, `cp .env.example .env`, `make secrets`, `make check-env` → Track B steps in §0.2 order (DevRev registration, Akamai account, Twilio, Linode token, bucket, optional AWS, SE questions), each ending with the `check-env` row that should turn READY → secrets rules (§0.5: one `.env` per checkout, laptop-only `LINODE_TOKEN` and AWS keys, how to copy `.env` to the VM without them) → the three phases and when each must pass (§0.4, §0.6) → after-event revocations (§0.5).
