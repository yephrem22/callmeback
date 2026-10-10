# Feature Specification: Cloud Infrastructure on Akamai

**Feature Branch**: `002-cloud-infra`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Host Call Me Back on Akamai Cloud. One VM in Chicago, behind a cloud firewall, runs the app and the DevRev connector behind an HTTPS reverse proxy on a free hostname. Object Storage keeps evidence. Deploying and backing up are one command each.
P1: The dashboard and API answer over HTTPS behind basic auth. Twilio webhooks and the MCP endpoint are reachable without basic auth. Internal routes are not reachable from outside.
P1: A redeploy takes under three minutes and survives a reboot.
P2: Provisioning is scripted and repeatable.
Details are in PLAN.md §16."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Public HTTPS edge with the right doors open (Priority: P1)

Builder B stands up one Linode VM in Chicago (us-ord) behind the `callmeback-fw` cloud firewall and puts the app and the MCP service behind an HTTPS reverse proxy on a free hostname of the form `<ip-with-dashes>.sslip.io` (PLAN.md §5, §16.1). From any laptop, the dashboard and `/api/*` answer over HTTPS only after basic auth; `/healthz`, `/twilio/*` and `/mcp` answer without basic auth (Twilio uses its signature check, the MCP service its Bearer token); `/internal/*` is a 404 from outside because it is reachable only inside the Docker network (PLAN.md §16.2 Caddyfile).

**Why this priority**: Nothing live can happen without it. Twilio must fetch TwiML from a public URL with a valid certificate (spec 006), DevRev must reach `/mcp` (spec 008), and the 7 PM checkpoint demo runs from this URL. Milestone B1 in PLAN.md §18 blocks on it.

**Independent Test**: With the three containers running and `.env` filled in, run `curl -s https://HOST/healthz` from a laptop and get `{"ok": true}` with a valid certificate; then probe each route class with and without credentials and compare the status codes to the table in FR-004 through FR-007. The integration gate `make check-env PHASE=integrate` shows the public URL row READY (PLAN.md §0.4).

**Acceptance Scenarios**:

1. **Given** the VM, firewall and `.env` are in place and `docker compose up -d --build` has finished, **When** a laptop requests `https://HOST/healthz`, **Then** it receives HTTP 200 with body `{"ok": true}` over a certificate the laptop trusts without warnings.
2. **Given** the edge is up, **When** a laptop requests the dashboard root or any `/api/*` path without credentials, **Then** it receives HTTP 401 with a basic-auth challenge; **When** it repeats the request with `DASH_USER` and the password behind `DASH_PASS_HASH`, **Then** the app answers.
3. **Given** the edge is up, **When** a request reaches `/twilio/*` or `/mcp` without basic-auth credentials, **Then** the proxy forwards it to the app or MCP service respectively, and only the service's own check (Twilio signature or Bearer token) decides the outcome.
4. **Given** the edge is up, **When** any outside client requests a path under `/internal/*`, **Then** it receives HTTP 404 and the request never reaches the app.
5. **Given** the firewall is attached, **When** a port other than 22, 80 or 443 is probed from the internet, **Then** the connection is dropped.

---

### User Story 2 - One-command redeploy and backup that survive a reboot (Priority: P1)

After the first deployment, Builder B (or Builder A over SSH) ships the current `main` to the VM with a single command, `scripts/deploy.sh`, and takes a database backup with a single command, `scripts/backup_db.sh` (PLAN.md §16.2). If the VM reboots, all three services come back on their own with the same certificate and data, and the public URL answers again without anyone typing a command.

**Why this priority**: The day has at least four scheduled deploys (B4, B7, the 7 PM checkpoint and the final 7:00 AM deploy, PLAN.md §18–§19) plus unscheduled fixes. Every minute a deploy takes is a minute off the voice and DevRev work, and a VM that does not come back after a reboot ends the demo.

**Independent Test**: Push a trivial change to `main`, run `scripts/deploy.sh` on the VM, time it, and confirm the change is visible at `https://HOST`. Reboot the VM from Cloud Manager and confirm `/healthz` answers again without intervention. Run `scripts/backup_db.sh` and confirm a timestamped copy of the database appears under `data/`.

**Acceptance Scenarios**:

1. **Given** a commit is on `main` that is not yet on the VM, **When** `scripts/deploy.sh` runs, **Then** it pulls fast-forward only, rebuilds and restarts the containers, prints their status, and the new code answers on the public URL in under three minutes end to end.
2. **Given** the VM is serving the app, **When** the VM is rebooted, **Then** the app, MCP and proxy containers restart automatically, the previously issued certificate is reused, data under `data/` is intact, and `/healthz` returns 200 again without any manual command.
3. **Given** the app is running and writing to its SQLite database, **When** `scripts/backup_db.sh` runs, **Then** a consistent copy named `data/app.<HHMM>.db` exists and the running app is not interrupted.
4. **Given** `.env` was edited on the VM after the first start, **When** `docker compose up -d` is run again, **Then** the containers pick up the new values (PLAN.md §16.1 step 5).

---

### User Story 3 - Evidence locker in Object Storage (Priority: P2)

Builder B creates the `callmeback-evidence-tenex` bucket in Chicago with a limited read/write access key scoped to that bucket, and fills `OBJ_ENDPOINT`, `OBJ_REGION`, `OBJ_BUCKET`, `OBJ_ACCESS_KEY` and `OBJ_SECRET_KEY` on the VM (PLAN.md §16.3). Once set, the app stores raw emails and audit exports as objects and the dashboard says "Evidence stored in Akamai Object Storage" instead of "Evidence stored locally" (PLAN.md §13.4).

**Why this priority**: It is PLAN.md priority P1 (milestone B4): it is a judged Akamai integration and makes the audit trail durable, but the app works end to end with `STORAGE_MODE=local` until the bucket exists (constitution principle V), so it never blocks the P1 stories above.

**Independent Test**: With the five `OBJ_*` variables set, `make check-env` reports the Object Storage row READY by putting, reading and deleting `healthcheck/<uuid>.txt` (PLAN.md §0.4). Ingesting a sample invoice on the VM then yields a `raw/{invoice_id}.eml` object and a working presigned link.

**Acceptance Scenarios**:

1. **Given** the bucket and limited key exist and the `OBJ_*` variables are set on the VM, **When** `make check-env` runs, **Then** the Object Storage row is READY and the probe object has been deleted afterwards.
2. **Given** storage is configured, **When** an invoice is ingested, **Then** a `raw/{invoice_id}.eml` object exists and the dashboard offers a presigned link valid for 15 minutes.
3. **Given** the bucket is unreachable, **When** an invoice is ingested, **Then** a warning is logged, the pipeline continues, and no payment decision changes (best effort, PLAN.md §13.4).
4. **Given** the access key is the limited one, **When** it is used against any other bucket, **Then** the request is refused.

---

### User Story 4 - Scripted, repeatable provisioning (Priority: P3)

Builder B can recreate the whole environment from a laptop with `scripts/provision_linode.sh`, driven by `LINODE_TOKEN` (laptop only, never on the VM, PLAN.md §0.4): the `callmeback-fw` firewall allowing 22, 80 and 443, a Linode 4 GB Ubuntu 24.04 instance in us-ord, the evidence bucket and its limited key. Running it twice changes nothing the second time, and it prints the public IP and the sslip.io hostname.

**Why this priority**: PLAN.md marks it P2. The manual Cloud Manager steps in §16.1 are the fallback and are fast enough for one VM; the script matters only if the VM must be rebuilt or the CLI proves quick.

**Independent Test**: Run the script against an account with no Call Me Back resources, confirm the firewall, instance and bucket exist with the stated settings, then run it again and confirm it exits successfully without creating duplicates.

**Acceptance Scenarios**:

1. **Given** a laptop with a valid `LINODE_TOKEN` and no existing resources, **When** the script runs, **Then** the firewall, instance and bucket are created with the settings in PLAN.md §16.1 and §16.3 and the IP and hostname are printed.
2. **Given** the resources already exist, **When** the script runs again, **Then** it reports them as present, creates nothing new and exits 0.
3. **Given** the CLI rejects a flag, **When** Builder B falls back to the Cloud Manager steps in PLAN.md §16.1, **Then** the result is indistinguishable to every other spec.

---

### Edge Cases

- Let's Encrypt refuses the sslip.io name: switch `HOST` and `PUBLIC_BASE_URL` to the Linode reverse-DNS name (`<ip-with-dashes>.ip.linodeusercontent.com`) and restart the proxy (PLAN.md §16.1 step 3, §16.5).
- `DASH_PASS_HASH` is a placeholder or lost its `$` signs: the proxy exits on start; the hash stays single-quoted in `.env` (PLAN.md §16.5).
- `MCP_TOKEN` is shorter than 32 characters or `eb_data/` is missing: the MCP container restarts in a loop; the other two services keep serving (PLAN.md §16.5).
- `MCP_ALLOWED_HOSTS` differs from `HOST`: `/mcp` returns 403 (PLAN.md §16.5).
- `PUBLIC_BASE_URL` does not exactly match the URL Twilio called: webhooks return 403 (PLAN.md §16.5).
- A container is down: the proxy returns 502; `docker compose ps` and `logs` locate it.
- The backup runs while the app is writing: the SQLite online backup produces a consistent copy; WAL mode is unaffected.
- `.env` is changed but the containers are not restarted: old values stay in effect until `docker compose up -d`.
- A fast-forward pull fails because the VM has local edits: deploy stops before rebuilding and reports the conflict instead of merging.
- `LINODE_TOKEN` or `AWS_*` lines are accidentally copied to the VM: the copy command in PLAN.md §16.1 filters them out; the VM `.env` must never contain them.
- Firewall default inbound policy left at Accept: the VM is exposed; the policy must be Drop with only 22, 80 and 443 accepted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST run on one Linode VM (Ubuntu 24.04 LTS, Linode 4 GB, region us-ord, label `callmeback`) per PLAN.md §16.1.
- **FR-002**: The VM MUST sit behind the `callmeback-fw` Akamai Cloud Firewall whose inbound policy is Drop except TCP 22, 80 and 443, with outbound allowed.
- **FR-003**: The public hostname MUST be `<ip-with-dashes>.sslip.io`, with `<ip-with-dashes>.ip.linodeusercontent.com` as the documented fallback, and the proxy MUST obtain and renew a publicly trusted certificate for it automatically using `ACME_EMAIL`.
- **FR-004**: The proxy MUST require basic auth (`DASH_USER`, `DASH_PASS_HASH`) for the dashboard and every path not listed in FR-005 through FR-007.
- **FR-005**: The proxy MUST forward `/healthz` and `/twilio/*` to the app without basic auth.
- **FR-006**: The proxy MUST forward `/mcp` (and paths under it) to the MCP service without basic auth; authentication there is the service's Bearer token (spec 008).
- **FR-007**: The proxy MUST answer 404 for `/internal/*` so those routes are reachable only from inside the Docker network.
- **FR-008**: The deployment MUST consist of three services (app, mcp, caddy) defined in `docker-compose.yml` exactly as in PLAN.md §16.2, each with `restart: unless-stopped`, with `data/` and `eb_data/` mounted from the host and the proxy's certificate state in named volumes.
- **FR-009**: The app image MUST be multi-stage: build the React dashboard, then the Python app, copying `core/`, `app/`, `samples/` and the built `web/dist`; the MCP image MUST copy `core/` and `mcp_server/`. Both build from the repo root (PLAN.md §5, §16.2).
- **FR-010**: A `.dockerignore` MUST exclude `.env`, `data/`, `eb_data/`, `web/node_modules`, `web/dist`, `web/snapshots`, `.claude/` and `.git` so no secret or local state enters an image.
- **FR-011**: `scripts/deploy.sh` MUST, in one command, pull `main` fast-forward only, rebuild and restart the services, and print their status.
- **FR-012**: `scripts/backup_db.sh` MUST, in one command, produce a consistent copy of `data/app.db` named `data/app.<HHMM>.db` without stopping the app.
- **FR-013**: The VM's `.env` MUST be created by hand over SSH from the laptop's `make secrets` output with `LINODE_TOKEN` and `AWS_*` lines removed, then edited for `HOST`, `PUBLIC_BASE_URL`, `MCP_ALLOWED_HOSTS`, `VOICE_MODE=twilio` and `AI_MODE=live`; it MUST never be committed, printed or copied into an image.
- **FR-014**: Object Storage MUST be a bucket `callmeback-evidence-tenex` in Chicago with a limited read/write key scoped to that bucket, exposed to the app through `OBJ_ENDPOINT`, `OBJ_REGION`, `OBJ_BUCKET`, `OBJ_ACCESS_KEY` and `OBJ_SECRET_KEY` (PLAN.md §16.3, §13.4).
- **FR-015**: Until the bucket exists, `STORAGE_MODE=local` MUST remain the default and the app MUST behave identically apart from where evidence is written (PLAN.md §13.4).
- **FR-016**: `scripts/provision_linode.sh` MUST be idempotent, create the firewall, instance, bucket and limited key with the settings above, print the public IP and sslip.io hostname, and run only from a laptop with `LINODE_TOKEN`.
- **FR-017**: The VM MUST also host the throwaway Twilio spike route for milestone B2 (PLAN.md §18) so a real call can be placed and timed before spec 006 is built; the route is removed once spec 006 lands.
- **FR-018**: Readiness MUST be verifiable with `make check-env PHASE=integrate`: the public URL row (200 on `/healthz` with a valid certificate) and, once configured, the Object Storage row (put, read, delete `healthcheck/<uuid>.txt`) per PLAN.md §0.4.

### Key Entities

- **VM**: the single Linode instance in us-ord that runs all three services; attributes are label, plan, image, public IPv4, attached firewall.
- **Firewall**: `callmeback-fw`; a fixed inbound allow list (22, 80, 443) with Drop default, attached to the VM.
- **Public hostname and certificate**: the sslip.io (or linodeusercontent fallback) name derived from the VM's IP, and its automatically issued certificate; referenced by `HOST` and `PUBLIC_BASE_URL`.
- **Route table**: the four route classes (basic-auth, Twilio, MCP, internal) and their auth boundary, as in PLAN.md §5 and the §16.2 Caddyfile.
- **VM environment file**: the hand-filled `.env` on the VM; a subset of the laptop's plus VM-specific values; never committed.
- **Evidence bucket and limited key**: `callmeback-evidence-tenex` and the key scoped to it; holds `raw/`, `audit/` and `ach/` objects (PLAN.md §13.4).
- **Deployment**: one run of `scripts/deploy.sh`, identified by the `main` commit it ships.
- **Backup**: a timestamped copy of the SQLite database under `data/`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a laptop outside the VM, `https://HOST/healthz` returns 200 with `{"ok": true}` and a certificate that passes default TLS validation, within 10 minutes of the first `docker compose up -d --build`.
- **SC-002**: Unauthenticated requests to the dashboard and `/api/*` return 401; the same requests with the configured credentials return the app's response; `/internal/*` returns 404 from outside; `/twilio/*` and `/mcp` are never challenged for basic auth. All verified by a scripted probe with zero mismatches.
- **SC-003**: A redeploy via `scripts/deploy.sh` completes, with the new code answering on the public URL, in under three minutes measured from the command's start.
- **SC-004**: After a VM reboot, `/healthz` returns 200 with the same certificate and the same data, with no manual command, within five minutes of the VM coming back.
- **SC-005**: `scripts/backup_db.sh` produces a readable copy of the database in under 10 seconds while the app keeps serving requests.
- **SC-006**: `make check-env PHASE=integrate` shows the public URL row READY by about 4 PM on build day (PLAN.md §0.4 gate), and the Object Storage row READY once milestone B4 is done.
- **SC-007**: `scripts/provision_linode.sh` run twice in a row leaves exactly one firewall, one instance, one bucket and one key, and exits 0 both times.
- **SC-008**: No secret value appears in the repository, any image layer, or any log produced by the deploy and backup scripts.

## Dependencies & Scope

- **Owner**: Builder B (milestones B1, B2 and B4 in PLAN.md §18).
- **Depends on**: spec 001 env-readiness, for `make secrets` (which generates `INTERNAL_TOKEN`, `MCP_TOKEN`, `DASH_USER`, `DASH_PASS_HASH`), `make check-env` and the `.env.example` fake modes.
- **Consumed by**: spec 006 (public URL for Twilio webhooks), spec 008 (`/mcp` for DevRev), spec 005 (`storage.py` targets the bucket), spec 009 (final deploy and backups).
- **PLAN.md sections covered**: §16.1–§16.3 and §16.5, §5 architecture, the Akamai Cloud API, Public HTTPS URL and Object Storage rows of §0.4, §13.4 Object Storage, and the B1/B2/B4 rows of §18.
- **Out of scope**: the app's own code (`app/storage.py` is spec 005's logic; this spec provides the bucket and variables), the voice module (spec 006), the MCP tools (spec 008), Twilio number configuration beyond §16.4, AWS fallback, any second region or VM, custom DNS domains.
- The VM's `.env` is filled by hand over SSH and never committed (FR-013). The Twilio spike (milestone B2) runs on this VM as a throwaway route and records dial, ring and answer timings in `docs/decisions.md` (FR-017).

## Assumptions

- The Akamai account has credit and quota for one Linode 4 GB instance, one firewall and one Object Storage bucket in Chicago.
- The free hostname providers behave as PLAN.md §16.1 describes: sslip.io resolves the dashed IP, and Let's Encrypt issues for it or the linodeusercontent fallback.
- Builder B has SSH access to the VM and a deploy key or fine-grained token to clone the repository onto it.
- The repository's `main` branch is always deployable; `deploy.sh` ships whatever is on `main` and does not run tests.
- Backups are kept on the VM's disk under `data/`; copying them off the VM is a manual step in milestone B10.
- One Uvicorn worker is enough for the demo load (PLAN.md §16.2); no horizontal scaling is needed.
- If the `linode-cli` flags prove troublesome, the Cloud Manager steps in PLAN.md §16.1 are an acceptable substitute for User Story 4 with no change to any other story.
