# Contract: serving the dashboard (PLAN.md §14.5; spec FR-024)

- `app/main.py` includes `/healthz`, `api.router` (`/api/*`) and the voice router (`/twilio/*`) first, then mounts `web/dist` at `/` **last**.
- A GET for an existing file under `web/dist` returns the file; `/` returns `index.html`.
- A GET for any other path returns `index.html` with 200 (the app shell; client-side routing decides), **except** paths under `/api/`, `/twilio/`, `/internal/`, `/mcp` and `/healthz`, which keep their real response (usually 404 or 405).
- Non-GET methods to unknown paths get 404/405, not the shell.
- When `web/dist/index.html` is absent (a dev checkout), nothing is mounted (unchanged).
- Caddy keeps basic auth in front of everything except `/healthz` and `/twilio/*` (spec 002, unchanged).
- Dev: `vite` serves the app on :5173 and proxies `/api` to :8000 (`web/vite.config.ts`, unchanged).
