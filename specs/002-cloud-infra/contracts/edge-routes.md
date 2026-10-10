# Contract: edge route table (PLAN.md §5, §16.2 Caddyfile; spec SC-002)

Verified by `scripts/probe_edge.sh HOST [DASH_USER DASH_PASSWORD]`.

| Request | Who answers | Expected |
|---|---|---|
| `GET /healthz` | app, no auth | 200 `{"ok": true}` |
| `GET /` no credentials | Caddy basic_auth | 401 with `WWW-Authenticate: Basic` |
| `GET /` with `DASH_USER:password` | app (web/dist or placeholder) | 200 |
| `GET /api/anything` no credentials | Caddy basic_auth | 401 |
| `POST /twilio/spike/status` no credentials | app | not 401 (204 from the spike route; 404 once spec 006 removes it and 403 from the signature check on real routes) |
| `POST /mcp` no Bearer | mcp service | 401 |
| `POST /mcp` wrong Host header | mcp service | 403 |
| `GET /internal/change-cases` | Caddy `respond 404` | 404, never reaches app |
| TLS | Caddy / Let's Encrypt | certificate valid for `HOST` with the default CA bundle (`curl --fail` succeeds) |
| any port other than 22/80/443 | Cloud Firewall | dropped (checked once by hand with `nc -z -w3 HOST 8000`) |
