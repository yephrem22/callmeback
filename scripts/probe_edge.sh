#!/usr/bin/env bash
# Edge route table check (spec 002 contracts/edge-routes.md, SC-002).
# usage: scripts/probe_edge.sh HOST [DASH_USER DASH_PASSWORD]
set -uo pipefail
HOST="${1:?usage: probe_edge.sh HOST [USER PASS]}"
USER_="${2:-}"; PASS="${3:-}"
BASE="https://$HOST"
fail=0

check() { # label expected actual
  if [ "$2" = "$3" ]; then printf 'OK        %-44s %s\n' "$1" "$3"; else printf 'MISMATCH  %-44s got %s, expected %s\n' "$1" "$3" "$2"; fail=1; fi
}
code() { curl -s -o /dev/null -m 15 -w '%{http_code}' "$@"; }

if curl -sS --fail -m 15 -o /dev/null "$BASE/healthz"; then check "TLS certificate valid (default CA bundle)" ok ok; else check "TLS certificate valid (default CA bundle)" ok FAILED; fi
check "GET /healthz"                        200 "$(code "$BASE/healthz")"
check "GET / without credentials"           401 "$(code "$BASE/")"
check "GET /api/invoices without credentials" 401 "$(code "$BASE/api/invoices")"
if [ -n "$USER_" ]; then
  check "GET / with credentials"            200 "$(code -u "$USER_:$PASS" "$BASE/")"
fi
# /twilio/* passes Caddy without basic auth, and the app's signature check refuses an unsigned
# request with 403 (spec 006, PLAN.md §12.2). 401 would mean Caddy is challenging Twilio.
check "POST /twilio/status/<random> unsigned → 403" 403 "$(code -X POST "$BASE/twilio/status/probe-$RANDOM$RANDOM")"
check "POST /mcp without Bearer"            401 "$(code -X POST "$BASE/mcp")"
check "GET /internal/change-cases"          404 "$(code "$BASE/internal/change-cases")"

if [ $fail -eq 0 ]; then echo "edge: all routes OK"; else echo "edge: MISMATCH (see above)"; fi
exit $fail
