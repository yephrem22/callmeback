# Decisions and kickoff answers

Record answers to the PLAN.md §2 and §22 questions here as they arrive, plus any decision that changes how we build. Newest at the bottom of each section.

## Setup facts (2026-10-10)

- Builder A: Yoseph. Builder B: Sahaj. Third teammate: Shubhangi. Repo created under Yoseph's GitHub account (yephrem22/callmeback).
- Reassignment, 2026-10-10 afternoon: Yoseph takes the Akamai work (spec 002 cloud-infra, inference key, Object Storage) in addition to 003, 005 and the UI specs 004/007; Sahaj keeps 001 and 006 and the vendor phone; Shubhangi takes 008 devrev-connector; 009 is shared. If Shubhangi finishes 008 early or stalls on DevRev access, she picks up the UI track (004/007).
- Spec 003 phase 1 landed on main 2026-10-10 (contracts frozen; 311 tests).
- Spec Kit 1.1.3, Python 3.12 (uv-managed), Node 22 installed on A's laptop at kickoff.
- Constitution v1.0.0 ratified 2026-10-10.
- Spec 001 (B): `requirements.txt` gained `twilio`, `boto3`, `bcrypt` (agreed with A); `.gitignore` is B-maintained with A's entries preserved; scripts run as modules (`make secrets` → `python -m scripts.gen_secrets`). `make check-env`, `make secrets`, `make test` are the shared entry points.

## Organizers (A)

1. Can Tenex.ai (Titanium sponsor) win cash? Does our team count as an official corporate team? — _pending_
2. Where and how do we submit, and what's required? — _pending_
3. Does our DevRev entry, which lives in DevRev Computer, count within our one project? — _pending_
4. When do sponsor judges see projects: table visits or the main stage? — _pending_

## DevRev solutions engineer (B)

1. Playground URL and invites for both builders — _pending_
2. Who can register custom MCP servers and publish org skills — _pending_
3. Enterprise-Bench export and its version manifest — _pending_
4. Is an HTTPS endpoint on an sslip.io hostname OK? — _pending_
5. Submission channel and demo format — _pending_

## AWS sponsor (A, optional)

- Event AWS accounts or Bedrock access? (Only for the optional fallback.) — _pending_

## Akamai

- Inference limits confirmed at kickoff? Is Object Storage included in the $300 credit? — _pending_

## Team

- Vendor phone line: B's phone (default). Presenter: A (default).
- Spec Kit tag that works: v1.1.3 (installed; no issues yet).

## Timings and spikes

- Twilio spike (B2), 2026-10-10 23:39 UTC on the VM (spec 002, Sahaj): queued 0.6 s → **ringing 1.1–1.7 s** after `calls.create` → answered by B after 17.5 s of ringing (human pick-up, not system latency) → Q1 prompt ~12 s → answer webhook accepted (Gather dtmf+speech) → completed at 37.6 s, call duration 19 s. Prompt was clear; "test is complete" heard. **Caller-ID was flagged as spam** by B's carrier and showed the payer name; mitigation per §16.4/§16.5: save the Twilio number as the contact "Call Me Back Verify" on the demo phone, and keep the other builder's phone as fallback. Twilio Voice geo-permissions had to be enabled for United States/Canada first (the API refused the call until then).
- LLM smoke test (A2), 2026-10-10 evening: structured output 3/3, tool calls 5/5 with stream off and on; decision **stream off** (`LLM_STREAMING=0`), `AI_MODE=live` is safe. Details in `docs/llm_smoke.md`.

## Contract changes (PLAN.md §7; both builders must agree)

- none yet

## Akamai setup facts (2026-10-10, Yoseph)

- Spec 002 ownership: returned to Sahaj (Builder B) on the evening of 2026-10-10; Yoseph had not started it and B's Linode token and Twilio account were live.
- VM (spec 002, Sahaj): Linode `callmeback` id 107867502, g6-standard-2, Ubuntu 24.04, us-ord, IPv4 172.232.17.115, firewall `callmeback-fw` (id 201518631, inbound DROP except TCP 22/80/443). `HOST=172-232-17-115.sslip.io`; Let's Encrypt issued the certificate about 5 s after the first `docker compose up`. Repo at `/opt/callmeback`, cloned over SSH agent forwarding (`ssh -A`), no deploy key. Fallback host if ever needed: `172-232-17-115.ip.linodeusercontent.com`.
- VM `.env`: copied with the §16.1 filtered command; `VOICE_MODE=simulated` and `AI_MODE=off` stay until spec 006's live phase and a clean inference probe. `OBJ_*` not yet set on the VM (needs the `callmeback-app` key secret from Yoseph, or a new limited key via `scripts/provision_linode.sh`).
- `app/main.py` is a minimal skeleton from spec 002 (`/healthz`, serves `web/dist`); spec 005 adds the §7.6 routers. `mcp_server/server.py` is a placeholder (401/403 behaviour only); spec 008 replaces it.

- Linode account `yephrem` with the $300 promo applied; laptop token scoped Account RO + Linodes/Firewalls/Object Storage RW.
- Object Storage bucket `callmeback-evidence-tenex` in us-ord. The endpoint Cloud Manager/API returned is `https://us-ord-10.linodeobjects.com` (cluster `us-ord-10`, not the `us-ord-1` placeholder in `.env.example`); `OBJ_REGION=us-ord-10`. Access key `callmeback-app` (id 6772570) is limited to that bucket. Put/get/delete and presigned URLs verified.
- Inference: the first key handed out was another team's spare and the gateway rejects it (`401 api key authentication failure: invalid credentials`) with the correct Bearer header and base URL. Waiting on a fresh team key; `AI_MODE=off` until it probes clean.
- `INTERNAL_TOKEN`, `MCP_TOKEN` and `DASH_PASS_HASH` were generated locally (same recipe as spec 001's `make secrets`); the dashboard password is in Yoseph's password manager.

## Strands 1.59.0 notes (spec 005; read before writing any agent code)

- The OpenAIModel streaming switch is `stream`, not `streaming` as PLAN.md §11.1 says. `streaming=` is silently ignored and streaming stays on (default True). `app/agents/model.py` passes `stream=`.
- Plugins must call `super().__init__()`: `Plugin.__init__` is where `@hook` methods are discovered. PLAN.md §11.3's `PaymentGuardPlugin.__init__` omits it, which would silently disable the payment guard.
- The Akamai gateway rejects `"tools": []` (HTTP 400). Strands always sends the field; `AkamaiModel` drops it when an agent has no tools.
