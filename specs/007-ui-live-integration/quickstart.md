# Quickstart: UI Live Integration (spec 007)

## Prerequisites

```bash
uv venv --python 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
cd web && npm ci && cd ..
```

## 1. Checks (no network)

```bash
AI_MODE=off .venv/bin/python -m pytest -q tests/test_fixtures_contract.py tests/test_spa_fallback.py
cd web && npm run typecheck && npm run lint && npm run build && cd ..
```

Expected: every fixture file and the exporter output match the InvoiceDetail shape, and unknown client paths return the app shell while `/api/*` keeps its 404.

## 2. Live dashboard (dev)

```bash
.venv/bin/python -m app.seed
AI_MODE=off VOICE_MODE=simulated DEMO_MODE=1 .venv/bin/python -m uvicorn app.main:app --port 8000
cd web && VITE_API_MODE=live npx vite --port 5173          # another terminal
```

Open http://localhost:5173 and walk through the five stories ([contracts/ui-data.md](contracts/ui-data.md)):
1. Load "Acme: urgent bank change". The queue selects it, and the case goes CALLING within about 1 s.
2. Open Demo controls → **Vendor says no**. Expect HELD with "Held. The vendor said no on the h:mm AM/PM call." and a SIMULATED badge on the callback.
3. **Try to make the AI pay**. The dialog names the layer, and the trace sheet opens.
4. **Reset demo**. The queue empties, and the case shows "Load a sample invoice to start."

## 3. The §19.1 story, automated

```bash
cd web && node scripts/snap.mjs --live --base http://localhost:5173 --api http://localhost:8000 --out snapshots/live
node scripts/snap.mjs --out snapshots/fixtures    # the prototype set, from fixtures mode (vite dev in fixtures mode)
```

Expected: every step screenshot in light and dark at 1024×576; no console errors; no non-localhost requests; every stamp change within 1.5 s of the API status change. Review `snapshots/live` against `snapshots/fixtures` and note differences in `docs/design/decisions.md`.

## 4. Production build served by FastAPI

```bash
cd web && npm run build && cd ..
AI_MODE=off .venv/bin/python -m uvicorn app.main:app --port 8000
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/some/client/path   # 200 (app shell)
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/nope           # 404
```

## 5. On the VM

Deploy as in spec 006 (git bundle, then `docker compose up -d --build app`). Reset, pre-run Heartland (press 1, then 4455), then run the §19.1 story with the real phone. If the phone doesn't ring within 15 s, use Demo controls → Vendor says no.
