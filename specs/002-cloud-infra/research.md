# Research: Cloud Infrastructure on Akamai

## R1. App Dockerfile when `web/` has no project yet

- **Decision**: keep the §16.2 two-stage shape, but the web stage copies `web/` wholesale and runs `npm ci && npm run build` only if `web/package.json` exists; otherwise it writes a one-line `dist/index.html` placeholder. The Python stage is §16.2 verbatim.
- **Rationale**: spec 004 has not created the Vite project (only `web/src/fixtures/` exists), and `COPY web/package.json` fails the build on a missing file. The conditional converges to §16.2 behaviour the moment `package.json` lands, with no further edit.
- **Alternatives**: wait for spec 004 (rejected: blocks the 7 PM checkpoint); a build arg to skip the stage (rejected: one more thing to get wrong on the VM).

## R2. `app/main.py` is A-owned and does not exist

- **Decision**: with Builder B's operator approval, create a minimal `app/main.py`: `FastAPI(title="Call Me Back")`, `GET /healthz → {"ok": true}` (§7.6), mount the B2 spike router when `DEMO_MODE`, and serve `web/dist` at `/` with an `index.html` fallback when the directory exists. Builder A adds the §7.6 routers in spec 005. Documented in `docs/decisions.md` and in the file's docstring.
- **Rationale**: the compose `CMD` is `uvicorn app.main:app`; without it nothing answers `/healthz` and SC-001 cannot be met.

## R3. `mcp_server/` does not exist (spec 008)

- **Decision**: create `mcp_server/Dockerfile` and `mcp_server/requirements.txt` (§16.2 and §6: `mcp==1.30.0`, `uvicorn`, `rapidfuzz`) and a placeholder `mcp_server/server.py`: a raw ASGI app on `MCP_PORT` that exits with a clear message if `MCP_TOKEN` is shorter than 32 characters (§16.5), returns 401 for any `/mcp` request without `Authorization: Bearer <MCP_TOKEN>`, 403 when the `Host` header is not in `MCP_ALLOWED_HOSTS`, and 404 elsewhere. Spec 008 replaces `server.py` with the real FastMCP service; the Dockerfile and requirements stay.
- **Rationale**: compose needs the image to build; `check-env`'s demo probe expects 401 on unauthenticated `POST /mcp`; the 403 host check mirrors §16.5 so the edge can be validated now.

## R4. Cloning a private repo onto the VM

- **Decision**: SSH agent forwarding. `scripts/bootstrap_vm.sh` is run as `ssh -A root@VM 'bash -s' < scripts/bootstrap_vm.sh`, and `make deploy` uses `ssh -A`, so `git clone`/`git pull` on the VM use the laptop's GitHub key for the duration of the command. Nothing is stored on the VM.
- **Rationale**: B's laptop key already authenticates to GitHub; a deploy key needs repo admin (Yoseph). Fallback documented: add a deploy key if a cron-style deploy is ever wanted.

## R5. VM `.env` values

- **Decision**: copy with the §16.1 command (`grep -v -E '^(LINODE_TOKEN|AWS_)' .env | ssh root@VM 'umask 077; cat > /opt/callmeback/.env'`), then on the VM set `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS` and a real `ACME_EMAIL`. Leave `VOICE_MODE=simulated` and `AI_MODE=off` until spec 006's live phase and the inference key probe clean (§16.1 names them as VM edits; this plan defers them to the owning specs: fail closed).
- **Rationale**: the §16.1 copy is the only path that keeps laptop-only keys off the VM; flipping modes before their specs exist would make the first live call hit a placeholder route.

## R6. Provisioning with `linode-cli` 5.69

- **Decision**: `scripts/provision_linode.sh` reads `LINODE_TOKEN` from `.env` into `LINODE_CLI_TOKEN` (never echoed), then idempotently: (1) firewall `callmeback-fw` with inbound `ACCEPT TCP 22,80,443`, `inbound_policy DROP`, `outbound_policy ACCEPT`; (2) instance label `callmeback`, `g6-standard-2`, `linode/ubuntu24.04`, `us-ord`, `--authorized_keys` from `~/.ssh/id_ed25519.pub`, a random root password that is generated and discarded; (3) attach the firewall; (4) bucket `callmeback-evidence-tenex` in `us-ord`; (5) limited key `callmeback-app` (read/write on that bucket) only if absent, since a key's secret is shown once. Prints the IPv4 and `<ip-with-dashes>.sslip.io`. Every flag is checked against `linode-cli <cmd> --help` before use.
- **Facts from the account (2026-10-10)**: no Linodes, no firewalls; limited key `callmeback-app` (id 6772570) exists; the bucket endpoint Cloud Manager returned is `https://us-ord-10.linodeobjects.com`, `OBJ_REGION=us-ord-10` (Yoseph's note in `docs/decisions.md`), not the `us-ord-1` placeholder of §7.1.
- **Alternatives**: Cloud Manager steps (§16.1) remain the fallback if the CLI fights.

## R7. Backups

- **Decision**: `sqlite3 data/app.db ".backup data/app.$(date +%H%M).db"` on the host (§16.2), with `sqlite3` installed by `bootstrap_vm.sh`. The online backup API is consistent under WAL without stopping the app.

## R8. Twilio spike (milestone B2)

- **Decision**: `app/voice/spike.py` (B-owned `app/voice/`) exposes `POST /twilio/spike/voice` (TwiML: a speech-and-keypad `Gather` with the §12.3 settings asking "press 1 or say yes") , `POST /twilio/spike/answer` (logs `Digits`/`SpeechResult`/`Confidence`, says thanks, hangs up) and `POST /twilio/spike/status` (logs `CallStatus` with a timestamp). No signature check (throwaway; removed by spec 006). `scripts/twilio_spike.py` on the laptop places the call with `status_callback_event=[initiated, ringing, answered, completed]` to `DEMO_VENDOR_PHONE` and polls the call resource; timings come from `docker compose logs app` on the VM.
- **Rationale**: FR-017 and §18 B2: measure dial → ring → answer and check caller ID before spec 006 is built.

## R9. Edge verification

- **Decision**: `scripts/probe_edge.sh HOST [USER PASS]` prints expected vs actual status for: `/healthz` (200), `/` without auth (401), `/` with auth (200), `/api/invoices` without auth (401), `/twilio/spike/status` POST without auth (not 401 from Caddy; app answers), `/mcp` POST without Bearer (401 from the MCP service), `/internal/change-cases` (404), and a TLS check via `curl --fail` with default CA bundle. Exit 1 on any mismatch (SC-002).
