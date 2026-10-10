# Implementation Plan: Cloud Infrastructure on Akamai

**Branch**: `002-cloud-infra` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

**Input**: `specs/002-cloud-infra/spec.md` and the Plan prompt in PLAN.md §23.2. Ownership note: PLAN.md §0.1 assigns 002 to Builder B; the afternoon reassignment in `docs/decisions.md` moved it to Builder A, and it moved back to B on 2026-10-10 evening because A had not started it and B's Linode token and Twilio account are live (recorded in `docs/decisions.md`).

## Summary

Stand up one Linode 4 GB Ubuntu 24.04 VM in us-ord behind the `callmeback-fw` firewall (22/80/443), running three containers from `docker-compose.yml`: `app` (FastAPI + `web/dist`), `mcp` (the DevRev connector) and `caddy` (HTTPS on `<ip-with-dashes>.sslip.io`, basic auth on the dashboard, open `/healthz`, `/twilio/*`, `/mcp`, 404 on `/internal/*`). Files follow PLAN.md §16.2 verbatim except where a dependency does not exist yet (research R1–R3). `scripts/deploy.sh` and `scripts/backup_db.sh` are one command each; `scripts/provision_linode.sh` creates the firewall, instance, bucket and limited key idempotently with `linode-cli`. The Twilio spike (milestone B2) runs on this VM as a throwaway route and its timings land in `docs/decisions.md`. Verification is `scripts/probe_edge.sh` (the route table of SC-002) and `make check-env PHASE=integrate` (public URL row READY).

## Technical Context

**Language/Version**: Bash scripts (`set -euo pipefail`), Dockerfiles, Compose v2 YAML, Caddy 2; Python 3.12 for the minimal `app/main.py` and the MCP placeholder.

**Primary Dependencies**: Docker 29 / Compose v5 on the VM (`get.docker.com`), `caddy:2` image, `python:3.12-slim`, `node:22-alpine`; `linode-cli` 5.69 on the laptop; `sqlite3` CLI on the VM for backups.

**Storage**: SQLite at `/srv/data/app.db` in the `app` container, bind-mounted from `/opt/callmeback/data`; Caddy certificate state in the named volumes `caddy_data`, `caddy_config`; evidence bucket `callmeback-evidence-tenex` (us-ord, endpoint `us-ord-10.linodeobjects.com`, research R6).

**Testing**: `tests/test_main_healthz.py` (FastAPI TestClient, no network); local `docker compose build` and an `app`-only `docker compose up` smoke on the laptop; on the VM, `scripts/probe_edge.sh` and `make check-env PHASE=integrate`; manual reboot, deploy-timing and backup checks from the spec's Independent Tests.

**Target Platform**: Ubuntu 24.04 LTS on Linode `g6-standard-2` in `us-ord`; laptop for provisioning only (`LINODE_TOKEN` never leaves it).

**Project Type**: infrastructure: container images, compose, proxy config, shell scripts, one tiny FastAPI module.

**Performance Goals**: redeploy under 3 minutes (SC-003); `/healthz` within 10 minutes of first `up` (SC-001); backup under 10 s (SC-005).

**Constraints**: `.env` never committed, printed or baked into an image (SC-008); `/internal/*` unreachable from outside; `restart: unless-stopped` on every service; `VOICE_MODE`/`AI_MODE` stay fake on the VM until their specs' live phases (fail closed, research R5); no edits to A-owned files except the agreed `app/main.py` skeleton (research R2).

**Scale/Scope**: one VM, three containers, ~9 files, ~400 lines.

## Constitution Check

| Principle | How this plan complies | Status |
|---|---|---|
| I. PLAN.md is the source of truth | compose, Caddyfile, deploy and backup scripts are §16.2 verbatim; the two deviations (web build stage, MCP placeholder) are documented in research R1/R3 and converge to §16.2 once specs 004/008 land. | PASS |
| II / III. Code holds the keys; fail closed | `/internal/*` is 404 at the edge; basic auth on everything else; the MCP placeholder answers 401 without the Bearer token; VM `.env` keeps `VOICE_MODE=simulated`, `AI_MODE=off` until the owning spec flips them. | PASS |
| IV. Call the number on file | the spike dials only `DEMO_VENDOR_PHONE`. | PASS |
| V. Never blocked by setup | nothing here is needed by the test suite; `STORAGE_MODE=local` stays default. | PASS |
| VI. Secrets stay in .env | `.dockerignore` excludes `.env`; the §16.1 copy command filters laptop-only keys; scripts never echo values; `LINODE_TOKEN` is read into the CLI's environment, not printed. | PASS |
| VII. Evidence everywhere | spike timings and VM facts are recorded in `docs/decisions.md`. | PASS |
| VIII. Test what is deterministic | `/healthz` has a unit test; the edge has a scripted probe; `make test` before each commit. | PASS |
| X. Small vertical slices | four phases, each stops and reports. | PASS |
| XI. Fresh code | all files written now; the Dockerfile shapes are from PLAN.md. | PASS |

Post-design re-check: no violations.

## Project Structure

```text
specs/002-cloud-infra/
├── plan.md, research.md, quickstart.md, tasks.md
└── contracts/edge-routes.md      # the SC-002 probe table

Dockerfile                        # §16.2, web stage tolerant of a missing web/package.json (R1)
.dockerignore                     # §16.2 list
docker-compose.yml                # §16.2 verbatim
Caddyfile                         # §16.2 verbatim
app/main.py                       # minimal: FastAPI app, /healthz, serve web/dist if present (R2; A extends in 005)
app/voice/__init__.py, spike.py   # B2 throwaway: /twilio/spike/* TwiML + status logging (R8); removed by spec 006
mcp_server/Dockerfile             # §16.2 verbatim
mcp_server/requirements.txt       # mcp==1.30.0, uvicorn, rapidfuzz (§6)
mcp_server/server.py              # placeholder: 401 without Bearer MCP_TOKEN, refuses short tokens (R3; spec 008 replaces)
scripts/deploy.sh                 # §16.2
scripts/backup_db.sh              # §16.2
scripts/provision_linode.sh       # idempotent linode-cli provisioning (R6)
scripts/bootstrap_vm.sh           # runs on the VM once: apt, docker, clone, data dirs (§16.1 step 4)
scripts/probe_edge.sh             # curl table for SC-002
scripts/twilio_spike.py           # laptop side of B2: place the spike call, print timings from status callbacks
tests/test_main_healthz.py
```

## Phases (each stops and reports)

1. **Containers and app skeleton, local (P0)**: all files above except provisioning, spike and probe; `docker compose build` on the laptop; `docker compose up app` answers `/healthz` on 8000; `tests/test_main_healthz.py`; `make test`. Commit.
2. **Provision and first deploy (P0, milestone B1)**: `provision_linode.sh` (run it), `bootstrap_vm.sh` over SSH with agent forwarding, VM `.env` via the §16.1 copy command, `docker compose up -d --build`, certificate, `probe_edge.sh` all green, `make check-env PHASE=integrate` public URL READY. Record IP/host in `docs/decisions.md` (not secrets). Commit.
3. **Operations (P0/P1, milestone B4)**: reboot test, timed `deploy.sh`, `backup_db.sh`, `OBJ_*` on the VM and Object Storage row READY (needs the key secret from Yoseph, or a new limited key). Commit.
4. **Twilio spike (milestone B2)**: `app/voice/spike.py`, `scripts/twilio_spike.py`, one real call to B's phone, dial/ring/answer timings and caller-ID observation in `docs/decisions.md`. Commit.

## Complexity Tracking

None.
