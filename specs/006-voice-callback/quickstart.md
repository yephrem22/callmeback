# Quickstart: Voice Callback Verification (spec 006)

## Prerequisites

```bash
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
```

Unit tests need nothing. Live calls need, in `.env` (check with `make check-env`, which masks values): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, `PUBLIC_BASE_URL` (spec 002's HTTPS host, no trailing slash), `DEMO_VENDOR_PHONE` (the builder's phone), `VOICE_MODE=twilio`, `TWILIO_VALIDATE_SIGNATURE=1`.

## 1. Unit tests (no network, zero credentials)

```bash
AI_MODE=off .venv/bin/python -m pytest -q tests/test_classify.py tests/test_twiml.py \
    tests/test_twilio_security.py tests/test_voice_flow.py tests/test_twilio_client.py
AI_MODE=off .venv/bin/python -m pytest -q          # the whole suite
```

Expected: the 11 classifier rows pass; tampered signatures get 403 with `webhook_rejected`; expired and superseded tokens hear the expiry message; every §17.1 voice-flow row passes ([contracts/twilio-routes.md](contracts/twilio-routes.md)).

## 2. Simulated mode (default, no phone)

```bash
.venv/bin/python -m app.seed && .venv/bin/python -m uvicorn app.main:app --port 8000
curl -s -XPOST localhost:8000/api/invoices/from-sample -H 'content-type: application/json' -d '{"name":"02_acme_fraud"}'
curl -s -XPOST localhost:8000/api/demo/simulate-answer -H 'content-type: application/json' \
     -d '{"subject_id":"<id>","answer":"no","last4":null}'
curl -s localhost:8000/api/invoices/<id>          # HELD / DENIED_BY_VENDOR, verification.source "simulated"
```

An unsigned webhook is refused:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -XPOST localhost:8000/twilio/status/anything   # 403
```

## 3. Live calls (on the VM, spec 002)

1. Set the Twilio variables and `VOICE_MODE=twilio` in the VM's `.env`; `docker compose up -d app`.
2. `scripts/probe_edge.sh`: `/twilio/status/<random>` answers 403 from outside, so Caddy passes it to the app without basic auth.
3. Fraud: load `02_acme_fraud` in the dashboard. The phone rings within 15 s and reads "Q1, invoice bank change" with "48,750 dollars". Say "No, we never changed banks". Expected: DENIED script, then HELD(DENIED_BY_VENDOR) within 3 s.
4. Heartland: load `03_heartland_bank_change`, press **1**, enter **4455#**. Expected: L4_OK, CONFIRMED, then RELEASED to ••••4455 and the vendor master updated.
5. No answer: load the fraud sample again and let it ring. Expected: HELD(NO_ANSWER) in about 35 s; Retry is offered.
6. Record the timings in `docs/decisions.md`.

If webhooks return 403 live, `PUBLIC_BASE_URL` does not exactly match the URL Twilio called (scheme, host, no trailing slash; PLAN.md §16.5). Fix the configuration; never set `TWILIO_VALIDATE_SIGNATURE=0` on the VM.
