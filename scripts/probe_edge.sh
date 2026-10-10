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
tw="$(code -X POST "$BASE/twilio/spike/status")"
if [ "$tw" = "401" ]; then check "POST /twilio/* not challenged for basic auth" "not-401" 401; else check "POST /twilio/* not challenged for basic auth" "not-401" "not-401"; echo "          (app answered $tw)"; fi
check "POST /mcp without Bearer"            401 "$(code -X POST "$BASE/mcp")"
check "GET /internal/change-cases"          404 "$(code "$BASE/internal/change-cases")"

if [ $fail -eq 0 ]; then echo "edge: all routes OK"; else echo "edge: MISMATCH (see above)"; fi
exit $fail
