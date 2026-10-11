# Call Me Back

**A second factor for money movement.** When an invoice email asks you to pay a new bank account, Call Me Back phones the vendor at the number you already have on file, never the one in the email, and only pays once they confirm. AI agents run the accounts-payable work; deterministic code decides whether money moves.

Built at Hack Midwest 2026 by team Tenex.ai, for the **Flex**, **AWS Strands Agents** and **Akamai Cloud** tracks.

---

## The problem

Last year US businesses lost about **$3 billion** to one kind of email: a supplier saying *"we changed banks, please pay the new account."* Google and Facebook once wired about $120 million to someone pretending to be their supplier. These scams work because the email looks right: the vendor's name, a real invoice number, an urgent tone, sometimes a domain one character off (`acme-supp1y.com`).

Every fraud guide recommends the same fix: **call the vendor back at a number you already trust** before changing where you send money. Almost nobody does it consistently, because it is slow and manual. And as accounts-payable work moves to AI agents, there is a new risk: an agent that can be talked into paying.

**Call Me Back makes that callback automatic, and makes AI-driven payments safe.**

## What it does

1. **Reads the invoice email.** Code extracts the amount, invoice number and bank details in milliseconds; an AI agent reads it too and fills gaps, but is never allowed to invent a number.
2. **Scores the risk with plain rules.** It compares the email with the vendor master (the company's own record of each vendor: trusted email domains, bank account, phone number) and adds points for a bank change, a lookalike domain, an unusual amount, a different reply-to address, pressure to pay fast, or language that discourages verification.
3. **Routes it.** Green pays automatically. Yellow goes to a person for review. Red triggers a **real phone call** to the vendor's number on file. An unknown vendor is held.
4. **Calls the vendor.** The line asks one clear question ("Did Acme request this bank change? Say yes or press 1. Say no or press 2."). For a bank change it also asks for the last four digits of the new account. A no, a wrong code, silence or a hang-up holds the payment.
5. **Pays through two locks.** An AI agent releases or holds the payment through a guarded tool. A plugin blocks the release unless policy allows it, and the ledger checks again before writing the payment. Money always goes to the account on file, never to one taken from an email.
6. **Records everything** in a hash-chained audit log and a live trace of every agent and tool call.

## The demo

Five sample emails cover the whole story:

| Sample | What's in it | Outcome |
|---|---|---|
| Acme: normal invoice | known vendor, same bank, usual amount | **0 points, GREEN → paid instantly** |
| Acme: urgent bank change | lookalike domain, new bank, 4× the usual amount, "pay today, don't call", a note telling AI assistants to skip the callback | **160 points, RED → phone call → vendor says no → HELD** |
| Heartland: legitimate bank change | real vendor, new account ending 4455 | **RED → call → press 1, enter 4455 → paid to the new account; vendor record updated** |
| Prairie Cloud: higher than usual | known vendor, about 2× the usual amount | **YELLOW → a person approves → paid** |
| Unknown vendor | nobody in the vendor master | **held: there is no trusted number to call** |

Then press **Try to make the AI pay**: a deliberately compromised agent is told by a fake CFO to release the held payment. It tries, and the trace shows it **blocked by the payment guard**.

## How the agents work

Four [Strands](https://strandsagents.com) agents, running on Akamai hosted inference, each with one narrow job. The rule behind them: **the AI explains; the code holds the keys.** An agent can make an outcome more cautious, never less.

| Agent | Sees | Does | Cannot |
|---|---|---|---|
| **Intake** | the email, labeled as untrusted input | extracts invoice fields, pressure phrases and AI-directed text | invent digits: a validator rejects any number not in the email and makes it try again |
| **Analyst** | read-only tools for this one invoice (findings, vendor record, history, email excerpt), all masked | writes a plain-English explanation of the risk | change the score or cite a flag that did not fire |
| **Verifier** | the exact question asked on the call and the speech-to-text answer | double-checks a spoken "yes" | turn a no into a yes; a keypad answer never needs it |
| **Payments** | `get_case_summary`, `release_payment`, `hold_payment`, bound to this invoice | releases or holds and writes a memo | release anything policy forbids: the payment-guard plugin cancels the tool, and the ledger re-checks |

Each agent has a timeout and a rules-only fallback, so a slow model never stops a decision. With AI switched off the product makes exactly the same money decisions; it just stops explaining, double-checking speech and acting through the agents.

## Sponsor tracks

### Flex: best FinTech app
A payment-destination verification layer for agentic bill pay:
- the **vendor master is the source of truth**: payments only ever go to the account on file, and changes need a verified callback;
- **out-of-band callback with a challenge-response** (the last four digits of the new account);
- **ABA routing-number checksum** on every extracted routing number;
- a **release/hold ledger** where the agent proposes and policy approves, with exactly one payment per invoice and an ACH effective date;
- **vendor-master change control** with before/after history, applied only after a confirmed call;
- a **hash-chained audit log** you can verify and export, framed as evidence for Nacha's fraud-monitoring rules.

### AWS: Strands Agents SDK
- **Four Strands agents** (Intake, Analyst, Verifier, Payments) on an OpenAI-compatible model.
- **The payment guardrail as a reusable Strands Plugin**: it uses `BeforeToolCallEvent.cancel_tool` to stop `release_payment` whenever policy says no, writes the decision to the trace and the audit log, and works for any agent you attach it to.
- **Structured output with Pydantic validators** that reject hallucinated digits; Strands re-asks automatically.
- **Tools bound to one invoice** by closure, so the model can never act on another record.
- A **trace plugin** that feeds the live "agent trace" panel, and a **rate-limit plugin** that shares the team's model quota and retries on throttling.
- The **"Try to make the AI pay"** red-team button: a compromised agent really calls `release_payment` and the plugin blocks it in front of you.
- An optional **Amazon Bedrock fallback** provider, tried once if the primary endpoint fails.

### Akamai: Cloud AI
- **Runs entirely on Akamai Cloud**: a Linode VM in Chicago (`us-ord`) behind an Akamai Cloud Firewall, with HTTPS from Caddy and Let's Encrypt.
- **Every model call goes to Akamai hosted inference** (`hackathon-chat`).
- The header shows **"Running on Akamai Cloud"** and the live inference latency (the median of recent model calls).
- **No chat box anywhere**: the AI works behind the scenes on real decisions, and the product keeps working with AI off if inference is slow.

## Architecture

```text
 invoice email ──▶ FastAPI app (Python 3.12) ─────────────────────────────▶ React dashboard
                   │  intake (regex + Intake agent)                        (Vite, Tailwind, shadcn/ui)
                   │  policy engine: score, tier, route   ◀── vendor master (SQLite)
                   │  callback ──▶ Twilio voice ──▶ vendor's phone on file
                   │  Payments agent ──▶ payment-guard plugin ──▶ ledger ──▶ ACH payment row
                   │  audit log (hash chain) + agent trace
                   └─ Strands agents ──▶ Akamai hosted inference
 Akamai Cloud VM (Chicago) · Docker Compose · Caddy (HTTPS, basic auth for the dashboard)
```

- **Backend:** FastAPI, SQLite (WAL), pydantic, Strands Agents, Twilio.
- **Frontend:** React, Vite, Tailwind CSS v4, shadcn/ui, TanStack Query (the dashboard polls; the open case refreshes every second).
- **Infra:** Docker Compose and Caddy on an Akamai Cloud (Linode) VM.

## Setup

### Requirements
- Python 3.12 and [`uv`](https://docs.astral.sh/uv/)
- Node.js 22+ and npm
- Docker (only for the VM deployment)

### Run it locally (no accounts needed)
Every integration has a fake mode, so the full product runs with zero credentials: AI off (rules only), a simulated phone line answered from the dashboard, and local storage.

```bash
git clone https://github.com/yephrem22/callmeback.git && cd callmeback
make install                  # creates .venv and installs requirements.txt
cp .env.example .env          # fake modes and placeholders everywhere
make secrets                  # app tokens and the dashboard login; prints the password once
make check-env                # readiness table with secrets masked; should end in PASS
.venv/bin/python -m app.seed  # demo vendors and payment history
make dev                      # API on http://localhost:8000
```

In a second terminal:

```bash
cd web && npm ci
VITE_API_MODE=live npm run dev    # dashboard on http://localhost:5173 (proxies /api to :8000)
```

Open http://localhost:5173, choose **Load a sample**, and use **Demo controls** to answer the simulated call. `npm run dev` without `VITE_API_MODE=live` runs the dashboard on built-in sample data with no backend at all.

### Turn on the real integrations
Add each value to `.env` and re-run `make check-env PHASE=integrate`; only that row changes. Never commit `.env` or paste its values anywhere.

| Integration | `.env` settings | Switch |
|---|---|---|
| Akamai hosted inference | `AKAMAI_BASE_URL`, `AKAMAI_API_KEY`, `MODEL_ID` | `AI_MODE=live` (or flip **AI live** in Demo controls) |
| Twilio voice | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `DEMO_VENDOR_PHONE`, `PUBLIC_BASE_URL` | `VOICE_MODE=twilio` (needs a public HTTPS URL for Twilio's webhooks) |
| Amazon Bedrock fallback (optional) | `AWS_REGION`, `BEDROCK_MODEL_ID`, AWS credentials | `LLM_FALLBACK=bedrock` |

`DEMO_VENDOR_PHONE` is the phone that rings in the demo: the seeded vendors use it as their number on file. Re-seed (or press **Reset demo**) after changing it.

### Deploy to Akamai Cloud
The VM runs the app and Caddy with Docker Compose from `/opt/callmeback`. Copy your `.env` to the VM without laptop-only secrets, set the VM's public host, then build:

```bash
grep -v -E '^(LINODE_TOKEN|AWS_)' .env | ssh root@<host> 'umask 077; cat > /opt/callmeback/.env'
ssh root@<host> 'cd /opt/callmeback && docker compose up -d --build'
scripts/probe_edge.sh <host>     # TLS, basic auth on the dashboard, Twilio webhooks reachable and signature-checked
```

On the VM set `HOST`, `PUBLIC_BASE_URL` (no trailing slash), `VOICE_MODE=twilio`, `AI_MODE=live` and `TWILIO_VALIDATE_SIGNATURE=1`. `docs/SETUP.md` has the full runbook.

## Tests

```bash
make test        # Python test suite plus the web typecheck, lint and build
```

About 730 tests run with no credentials and no network: the scoring vectors for every sample, the payment ledger rules, the audit chain, the four agents on scripted fake models, the guardrail and red-team tests, Twilio signature and token checks, every phone-call path through signed webhooks, the HTTP API, and a contract test that keeps the dashboard's sample data in sync with the real API.

The dashboard also has an end-to-end check that plays the whole demo against a running backend at projector size, in light and dark mode, and fails on any console error, any third-party request, or a screen that lags the backend by more than 1.5 seconds:

```bash
cd web && node scripts/snap.mjs --live --api http://localhost:8000
```

## Repository layout

```text
app/          FastAPI app: intake, policy engine, ledger, audit log, pipeline, HTTP API
app/agents/   the four Strands agents, the plugins (payment guard, trace, rate limit) and the runner
app/voice/    Twilio calls, webhook security, the call scripts and the answer classifier
core/         pure checks shared across the app (ABA checksum, lookalike domains, phrase lists)
web/          the React dashboard
samples/      the five demo invoice emails
scripts/      setup, readiness checks, edge probe, sample-data export
tests/        the test suite
specs/        the Spec Kit specs this was built from (PLAN.md is the source of truth)
docs/         setup runbook, design decisions, pipeline and voice notes
```

## Security notes
- Secrets live only in `.env`; `make check-env` reports their status with values masked.
- Twilio webhooks are authenticated by signature and a one-time, hashed URL token, and tokens never appear in logs.
- Account and phone numbers are masked to the last four digits everywhere outside the database, including model prompts.
- The callback always dials the vendor's number on file, and payments always go to the vendor's account on file.
