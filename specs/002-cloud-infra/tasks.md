# Tasks: Cloud Infrastructure on Akamai

**Input**: plan.md, research.md (R1–R9), contracts/edge-routes.md, quickstart.md, spec.md. PLAN.md §16 is the source for every file shape.

**Tests**: `tests/test_main_healthz.py` (unit, offline); the rest of this spec is verified live by `scripts/probe_edge.sh`, `make check-env PHASE=integrate` and the manual checks in quickstart.md, recorded in the phase reports and `docs/decisions.md`.

**Organization**: four phases from plan.md: US1 edge (phases 1–2), US2 operations (phase 3), US3 evidence bucket (inside phase 3), the B2 spike (phase 4). US4 provisioning script is built in phase 2 because it is the fastest way to get the VM.

## Phase 1: Containers and app skeleton, local (US1, P1)

- [x] T001 Create `app/main.py` (research R2): `FastAPI(title="Call Me Back")`, `GET /healthz` returning `{"ok": True}` (PLAN.md §7.6), include `app.voice.spike.router` when `config.S.demo_mode` and the module exists, and if `web/dist/index.html` exists mount `StaticFiles(directory="web/dist", html=True)` at `/` **after** the routers. Docstring: "minimal skeleton created by spec 002; spec 005 adds the §7.6 routers".
- [x] T002 [P] Create `tests/test_main_healthz.py`: `TestClient(app).get("/healthz")` → 200 and `{"ok": True}`; `/internal/change-cases` → 404 from the app (nothing mounted); no network.
- [x] T003 [P] Create `Dockerfile` per PLAN.md §16.2 with the research R1 web stage (`COPY web/ ./` then `RUN if [ -f package.json ]; then npm ci && npm run build; else mkdir -p dist && printf '<!doctype html><title>Call Me Back</title><p>Dashboard not built yet (spec 004).</p>' > dist/index.html; fi`), Python stage verbatim (`COPY requirements.txt`, `pip install`, `COPY core app samples`, `COPY --from=web /web/dist ./web/dist`, `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`).
- [x] T004 [P] Create `.dockerignore` with `.env`, `.env.local`, `data/`, `eb_data/`, `web/node_modules`, `web/dist`, `web/snapshots`, `.claude/`, `.git`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `specs/`, `docs/` (§16.2 list plus obvious local state).
- [x] T005 [P] Create `docker-compose.yml` exactly as PLAN.md §16.2 (three services, `env_file: .env`, `./data:/srv/data`, `./eb_data:/eb_data:ro`, ports 80/443 on caddy, named volumes `caddy_data`, `caddy_config`, `restart: unless-stopped`).
- [x] T006 [P] Create `Caddyfile` exactly as PLAN.md §16.2.
- [x] T007 [P] Create `mcp_server/Dockerfile` (§16.2 verbatim), `mcp_server/requirements.txt` (`mcp==1.30.0`, `uvicorn==0.54.0`, `rapidfuzz==3.14.6`), `mcp_server/__init__.py`, and the placeholder `mcp_server/server.py` per research R3 (raw ASGI app; exits 1 with "MCP_TOKEN must be 32+ characters" if short; 403 when `Host` not in `MCP_ALLOWED_HOSTS` (comma-separated, compare hostname without port); 401 on `/mcp*` without `Authorization: Bearer <MCP_TOKEN>`; 200 `{"placeholder": true}` with the right token; 404 elsewhere; `python -m mcp_server.server` runs uvicorn on `MCP_PORT`). Docstring: "placeholder from spec 002; spec 008 replaces this file".
- [x] T008 [P] Create `scripts/deploy.sh` (§16.2: `cd /opt/callmeback && git pull --ff-only && docker compose up -d --build && docker compose ps`, `set -euo pipefail`, prints elapsed seconds) and `scripts/backup_db.sh` (§16.2: `sqlite3 data/app.db ".backup data/app.$(date +%H%M).db"`, prints the file and its size). `chmod +x` both.
- [x] T009 Local smoke: `docker compose build` succeeds for `app` and `mcp`; `docker compose run --rm -p 8000:8000 app` (or a temporary port mapping) answers `curl localhost:8000/healthz` → `{"ok": true}`; `mcp` container with a 40-char `MCP_TOKEN` answers 401 on `POST /mcp` and 403 on a wrong Host; tear down. `make test` green. Commit: `spec 002 phase 1: compose, Caddyfile, images, deploy and backup scripts, app skeleton`.

**Checkpoint**: images build and the app answers locally. Tell Builder A that `app/main.py` exists. Stop and report.

## Phase 2: Provision and first deploy (US1 + US4, milestone B1)

- [x] T010 Create `scripts/provision_linode.sh` per research R6 with flags verified against `linode-cli … --help`: reads `LINODE_TOKEN` from `.env` with python-dotenv into `LINODE_CLI_TOKEN`; `--json` for lookups; firewall by label, instance by label, bucket by label, key by label; prints `IPV4=` and `HOST=<dashed>.sslip.io`; exits 0 on a second run with "present" lines. Never prints the token or a key secret except the new key's secret once, clearly labelled, when it creates one.
- [x] T011 [P] Create `scripts/bootstrap_vm.sh` (runs on the VM via `ssh -A root@IP 'bash -s' < …`): `apt-get update && apt-get -y upgrade && apt-get -y install git sqlite3`, `curl -fsSL https://get.docker.com | sh`, `ssh-keyscan github.com >> ~/.ssh/known_hosts`, `git clone git@github.com:yephrem22/callmeback.git /opt/callmeback` if absent, `mkdir -p /opt/callmeback/{data,eb_data}`; idempotent.
- [x] T012 [P] Create `scripts/probe_edge.sh` per research R9 / contracts/edge-routes.md: prints `OK`/`MISMATCH` per row, exit 1 on any mismatch.
- [x] T013 Run `scripts/provision_linode.sh`; wait for the instance to boot; run `bootstrap_vm.sh`; copy `.env` with the §16.1 command; set `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS`, `ACME_EMAIL` on the VM via `sed`; `docker compose up -d --build`; watch caddy logs for the certificate. If Let's Encrypt refuses sslip.io, switch to `<dashed>.ip.linodeusercontent.com` (§16.1 step 3).
- [x] T014 Verify: `scripts/probe_edge.sh HOST demo '<password>'` all OK; `make check-env PHASE=integrate` shows Public HTTPS URL READY; `nc -z -w3 HOST 8000` fails (firewall). Update `Makefile` `deploy` target to `ssh -A` (research R4). Record IP, host and the time to first certificate in `docs/decisions.md` (no secrets). Commit: `spec 002 phase 2: provisioning, VM bootstrap, edge probe; VM live`.

**Checkpoint**: `https://HOST/healthz` answers from a laptop. Stop and report with the probe table.

## Phase 3: Operations (US2 + US3, milestone B4)

- [x] T015 Timed redeploy: push a trivial commit to `main` (or merge this branch first), `time make deploy`, confirm the change on the public URL, record seconds (< 180) in `docs/decisions.md`.
- [x] T016 Reboot test: `ssh root@IP reboot`, poll `/healthz` until 200, confirm the certificate serial is unchanged (`openssl s_client`), confirm `data/` intact; record the recovery time.
- [x] T017 Backup: `ssh root@IP 'cd /opt/callmeback && bash scripts/backup_db.sh'` while the app serves; confirm `data/app.<HHMM>.db` opens with `sqlite3 … 'pragma integrity_check'`.
- [x] T018 Object Storage on the VM: obtain the `callmeback-app` key secret from Yoseph (or create a new limited key with `provision_linode.sh`), set the five `OBJ_*` lines on the VM's `.env` (`OBJ_ENDPOINT=https://us-ord-10.linodeobjects.com`, `OBJ_REGION=us-ord-10`), `docker compose up -d`, and confirm `make check-env PHASE=integrate` on the laptop (with the same values) shows Object Storage probe ok. Keep `STORAGE_MODE=local` until `app/storage.py` exists.
- [x] T019 `make test`; commit: `spec 002 phase 3: ops verified (deploy, reboot, backup, object storage)`.

## Phase 4: Twilio spike (milestone B2, FR-017)

- [x] T020 Create `app/voice/__init__.py` and `app/voice/spike.py` per research R8 (`APIRouter(prefix="/twilio/spike")`, routes `voice`, `answer`, `status`; `async def`; JSON log lines with `ts`, `event`, `CallStatus`/`Digits`/`SpeechResult`/`Confidence`; TwiML via `twilio.twiml.voice_response`). Mount from `app/main.py` only when `DEMO_MODE`.
- [x] T021 [P] Create `scripts/twilio_spike.py`: reads `.env` via dotenv, places one call to `DEMO_VENDOR_PHONE` with `url=PUBLIC_BASE_URL/twilio/spike/voice`, `status_callback=…/twilio/spike/status`, events initiated/ringing/answered/completed, `timeout=25`; polls the call until completed and prints the status timeline with timestamps. Refuses to run if `PUBLIC_BASE_URL` is a placeholder.
- [x] T022 Deploy, run the spike, answer the phone (press 1 or say yes), collect timings from `docker compose logs app`; record dial/ring/answer seconds and the caller-ID shown in `docs/decisions.md` "Timings and spikes". `make test`; commit: `spec 002 phase 4: Twilio spike route and timings`.

## Phase 5: Converge and merge

- [ ] T023 Tick tasks, note in `docs/decisions.md` that 002 returned to B and that `app/main.py` and `mcp_server/server.py` are skeletons for specs 005 and 008.
- [ ] T024 Rebase on `origin/main`, `make test`, push, fast-forward `main`, tell A and Shubhangi.

## Dependencies

Phase 1 → 2 → 3; phase 4 needs phase 2 (public URL) and can run before or after 3. T001 before T002 and T009; T003–T008 parallel; T010–T012 parallel before T013.
