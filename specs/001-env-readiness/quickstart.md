# Quickstart: validating Environment Readiness

Prerequisites: Python 3.12 and `uv` (PLAN.md §0.3). No credentials needed for anything below except the last section.

## 1. Zero-credential pass (spec US2, SC-001, SC-003)

```bash
make install                      # .venv with requirements.txt
rm -f .env                        # start from nothing (or use a fresh clone)
make check-env                    # expect: every row MISSING or FAKE; "build gate: PASS (exit 0)"
echo $?                           # 0
cp .env.example .env
make check-env                    # expect: Akamai/Object Storage/Twilio/AWS FAKE; App secrets FAILED
echo $?                           # 1  (placeholder tokens and hash are malformed, §0.4)
make test                         # pytest -q green, no network
```

## 2. Secrets (spec US3, SC-006)

```bash
make secrets                      # prints the dashboard password once
sha256sum .env > /tmp/env.before
make secrets                      # "Nothing to do"
sha256sum -c /tmp/env.before      # OK: byte-identical
make check-env                    # App secrets READY; exit 0
grep -c "^DASH_PASS_HASH='\$2a\$14\$" .env   # 1
```

## 3. Masking and JSON (spec FR-004, FR-005, SC-002)

```bash
make check-env ARGS="--json" | python3 -c "import json,sys; r=json.load(sys.stdin); print(r['phase'], r['ok'], len(r['rows']))"
# build True 8
# With a real key in .env, confirm only its last 4 characters ever appear:
make check-env ARGS="--json" | grep -c "$(python3 -c "from dotenv import dotenv_values as d; print(d('.env')['AKAMAI_API_KEY'][:-4])")"
# 0
```

## 4. Phase gates with no live integrations (spec US1 AC3)

```bash
make check-env PHASE=integrate; echo $?    # 1; failures name Akamai inference, public URL, Twilio
make check-env PHASE=demo; echo $?         # 1; failures also name AI_MODE, VOICE_MODE, /mcp, EB_DATASET_VERSION, balance
```

## 5. Guardrails (spec US4, SC-008)

```bash
git status --short | grep -E '^\?\? \.env' ; echo "exit $?"    # exit 1: .env is ignored
cat .worktreeinclude                                            # .env
cat .claude/settings.json                                       # the §0.5 deny rules
# In a Claude Code session: Read ./.env is denied; Read .env.example succeeds.
```

## 6. Turning rows READY (needs credentials; spec SC-007)

Fill one value at a time and re-run `make check-env`; only that row changes:

| you add to `.env` | row that turns READY | evidence shown |
|---|---|---|
| `AKAMAI_API_KEY` (keep `AI_MODE=off`) | Akamai inference stays FAKE, evidence shows "probe ok, N ms" under `PHASE=integrate` | latency |
| `LINODE_TOKEN` | Akamai Cloud API | Linode username |
| `OBJ_ACCESS_KEY`, `OBJ_SECRET_KEY` (keep `STORAGE_MODE=local`) | Object Storage stays FAKE; probe ok in evidence | bucket name |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Twilio FAKE with probe ok (or FAILED with the reason: trial, balance, voice) | balance, number ••••-last4 |
| `HOST`, `PUBLIC_BASE_URL` (after spec 002) | Public HTTPS URL | 200 and certificate OK |

Optional, places exactly one call to your phone: `make check-env ARGS="--call-test"`.

The integrate gate (`make check-env PHASE=integrate`) should pass by about 4 PM (PLAN.md §0.6); the demo gate needs `AI_MODE=live`, `VOICE_MODE=twilio`, the deployed `/mcp` and the SE's `EB_DATASET_VERSION`.
