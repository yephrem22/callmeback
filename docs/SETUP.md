# Setup runbook (Builder B track)

The ordered human steps from PLAN.md §0.2 (Track B), §0.3, §0.4 and §0.5, each ending with a check you can see. Nothing here blocks coding: every integration runs in a fake mode until its row turns READY (constitution V). **Never paste a value into chat, a spec, a prompt or git.** Share values with the other builder through a password manager or a direct message.

## 1. Tools (§0.3)

- git, Python 3.12, `uv`, Node.js 22+ with npm, Claude Code (latest), Spec Kit CLI 1.1.3.
- Docker (optional on laptops; required on the VM).
- Builder B only: `uv tool install linode-cli` and an SSH key: `ssh-keygen -t ed25519`.
- Optional: AWS CLI v2, only for the Bedrock fallback.

Check: `python3 --version` shows 3.12, `uv --version`, `node --version`, `linode-cli --version`.

## 2. First five minutes

```bash
git clone git@github.com:yephrem22/callmeback.git && cd callmeback
make install                 # .venv from requirements.txt
cp .env.example .env         # every fake mode selected; placeholders everywhere
make secrets                 # INTERNAL_TOKEN, MCP_TOKEN, DASH_USER, DASH_PASS_HASH
make check-env               # build gate: PASS
make test                    # all green, no credentials, no network
```

`make secrets` prints the dashboard password **once**. Save it in the password manager; only its bcrypt hash is stored. To get a new one, delete the `DASH_PASS_HASH` line and run `make secrets` again.

Check: `make check-env` ends with `build gate: PASS (exit 0)`; the App secrets row is READY; every other row is FAKE or MISSING.

## 3. Accounts and keys, in PLAN.md §0.2 order

Put each value in `.env` as it arrives and re-run `make check-env`. Only that row changes.

| When | Step | `.env` lines | Check |
|---|---|---|---|
| T+0 | Register for the DevRev challenge with B as team contact: https://forms.gle/7civKxbEtoo5Q4w77 | — | form sent |
| T+5 | Create the Akamai Cloud account with the $300 promo link (PLAN.md §2) and finish verification. Activation can lag | — | Cloud Manager shows the credit |
| T+10 | Twilio: upgrade (add a card, prepay about $20), buy **one US local number with Voice** (no SMS/MMS; local, not toll-free), complete the compliance profile as an individual, confirm **Voice → Geographic Permissions** includes the United States, save the number on your phone as "Call Me Back Verify" | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` (E.164), `DEMO_VENDOR_PHONE` (your phone, E.164) | `make check-env PHASE=integrate`: Twilio shows "probe ok, Full account, balance …"; FAILED names the reason (trial, balance under $10, no voice) |
| T+20 | (Builder A) get the Akamai inference key from the organizers | `AKAMAI_API_KEY` | `PHASE=integrate`: Akamai inference "probe ok, N ms". Set `AI_MODE=live` once spec 005's smoke test passes |
| T+25 | Linode personal access token: Account **read-only**; Linodes, Firewalls, Object Storage **read/write**; shortest expiry. Then `linode-cli configure --token` | `LINODE_TOKEN` (**laptop only**) | Akamai Cloud API READY with your username |
| T+30 | Object Storage: bucket `callmeback-evidence-tenex` in Chicago; an access key **limited to that bucket**; copy the exact endpoint from Cloud Manager (§16.3) | `OBJ_ENDPOINT`, `OBJ_REGION`, `OBJ_BUCKET`, `OBJ_ACCESS_KEY`, `OBJ_SECRET_KEY` | `PHASE=integrate`: Object Storage "probe ok" (a put/get/delete of `healthcheck/<uuid>.txt`). Set `STORAGE_MODE=s3` when spec 002's `storage.py` lands |
| T+35 | Optional: AWS keys with Bedrock access | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BEDROCK_MODEL_ID`, `LLM_FALLBACK=bedrock` (**laptop only**) | AWS READY, or leave `LLM_FALLBACK=none` (FAKE, never required) |
| T+40 | DevRev SE questions (PLAN.md §2): playground invites for A and B, admin and publisher roles, the Enterprise-Bench export and its version, sslip.io OK?, submission channel. Record answers in `docs/decisions.md` | `DEVREV_ORG_URL` (not secret), later `EB_DATA_DIR`, `EB_DATASET_VERSION` | DevRev row: data folders found, token 32+ chars. `public-<date>` as the version means the public release (FAKE) |
| T+75 | Spec 002: provision the VM (PLAN.md §16.1) | `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS` (= `HOST`), `ACME_EMAIL` | Public HTTPS URL READY: `/healthz` 200 with a valid certificate |

## 4. The three gates (§0.4, §0.6)

| Command | Passes when | Needed by |
|---|---|---|
| `make check-env` | app secrets are well-formed; MISSING and FAKE never fail it | always |
| `make check-env PHASE=integrate` | Akamai inference, public URL and Twilio probes READY (fake modes may still be selected) | about 4 PM Saturday, ahead of the 7 PM checkpoint |
| `make check-env PHASE=demo` | integrate, plus `AI_MODE=live`, `VOICE_MODE=twilio`, unauthenticated `POST /mcp` → 401, the SE's `EB_DATASET_VERSION`, Twilio balance ≥ $10 | the Sunday 7:00 final deploy |

Useful flags: `make check-env ARGS="--json"` for agents and scripts; `make check-env ARGS="--call-test"` places **one** call to `DEMO_VENDOR_PHONE` (the only way a call is ever placed by this command). Probes time out after 8 s each; a hung integration fails only its own row.

## 5. Secrets rules (§0.5)

- One gitignored `.env` per checkout (each laptop and the VM). `.env.example` is committed with fake values and is the only env file agents may read.
- `.worktreeinclude` lists `.env`, so Claude Code copies it into every worktree it creates. `.claude/settings.json` denies the Read tool on `.env` and `.env.local`; agents use `make check-env`, which masks every value to its last four characters.
- **Laptop only, never on the VM:** `LINODE_TOKEN` and the `AWS_*` keys. Copy `.env` to the VM without them (PLAN.md §16.1):
  ```bash
  grep -v -E '^(LINODE_TOKEN|AWS_)' .env | ssh root@<VM-IP> 'umask 077; cat > /opt/callmeback/.env'
  ```
  then on the VM edit `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS`, `VOICE_MODE=twilio`, `AI_MODE=live`, and run `docker compose up -d` again after any later change.
- `DASH_PASS_HASH` stays in **single quotes** so its `$` signs survive Docker Compose and python-dotenv. Caddy will not start on a placeholder or mangled hash (§16.5).
- `TWILIO_VALIDATE_SIGNATURE=1` always on the VM.

## 6. After the event (§0.5)

1. Revoke the Linode token and the Object Storage key in Cloud Manager.
2. Rotate the Twilio auth token.
3. Delete the MCP token (and the DevRev connection that uses it).
4. Delete or power off the VM once the $300 credit is no longer needed.
