#!/usr/bin/env bash
# Idempotent Akamai Cloud provisioning (PLAN.md §16.1, §16.3; spec 002 research R6).
# Laptop only: reads LINODE_TOKEN from .env (never printed). Creates, or reports as present:
#   firewall callmeback-fw (inbound DROP except TCP 22,80,443; outbound ACCEPT)
#   Linode `callmeback`: g6-standard-2, linode/ubuntu24.04, us-ord, your SSH key, firewall attached
#   Object Storage bucket callmeback-evidence-tenex in us-ord, and the limited key callmeback-app
# Prints IPV4= and HOST=<ip-with-dashes>.sslip.io at the end.
# linode-cli handles the firewall and the instance; this CLI build has no bucket commands, so the
# bucket and key go through the REST API with curl.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
PY="${PY:-$( [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3 )}"

FW_LABEL="${FW_LABEL:-callmeback-fw}"
VM_LABEL="${VM_LABEL:-callmeback}"
REGION="${REGION:-us-ord}"
VM_TYPE="${VM_TYPE:-g6-standard-2}"
IMAGE="${IMAGE:-linode/ubuntu24.04}"
BUCKET="${BUCKET:-callmeback-evidence-tenex}"
KEY_LABEL="${KEY_LABEL:-callmeback-app}"
SSH_PUB="${SSH_PUB:-$HOME/.ssh/id_ed25519.pub}"
API="https://api.linode.com/v4"

export LINODE_CLI_TOKEN
LINODE_CLI_TOKEN="$("$PY" -c "from dotenv import dotenv_values as d; print(d('.env').get('LINODE_TOKEN') or '')")"
if [ -z "$LINODE_CLI_TOKEN" ] || [[ "$LINODE_CLI_TOKEN" == *replace* ]]; then
  echo "LINODE_TOKEN is not set in .env (laptop only; PLAN.md §0.2 T+25)" >&2; exit 1
fi
command -v linode-cli >/dev/null || { echo "linode-cli missing: uv tool install linode-cli" >&2; exit 1; }
[ -f "$SSH_PUB" ] || { echo "SSH public key $SSH_PUB missing: ssh-keygen -t ed25519" >&2; exit 1; }

api() { # method path [json]
  curl -sS -H "Authorization: Bearer $LINODE_CLI_TOKEN" -H "Content-Type: application/json" -X "$1" "$API$2" ${3:+-d "$3"}
}
jq_() { "$PY" -c "import json,sys; $1" ; }

# ---- 1. firewall ---------------------------------------------------------------
FW_ID="$(linode-cli firewalls list --json | jq_ "print(next((f['id'] for f in json.load(sys.stdin) if f['label']=='$FW_LABEL'), ''))")"
if [ -n "$FW_ID" ]; then
  echo "firewall $FW_LABEL present (id $FW_ID)"
else
  RULES='[{"label":"allow-ssh-http-https","action":"ACCEPT","protocol":"TCP","ports":"22,80,443","addresses":{"ipv4":["0.0.0.0/0"],"ipv6":["::/0"]}}]'
  FW_ID="$(linode-cli firewalls create --label "$FW_LABEL" --rules.inbound_policy DROP --rules.outbound_policy ACCEPT \
            --rules.inbound "$RULES" --json | jq_ "print(json.load(sys.stdin)[0]['id'])")"
  echo "firewall $FW_LABEL created (id $FW_ID)"
fi

# ---- 2. instance ---------------------------------------------------------------
VM_JSON="$(linode-cli linodes list --json | jq_ "print(json.dumps(next((l for l in json.load(sys.stdin) if l['label']=='$VM_LABEL'), {})))")"
VM_ID="$(printf '%s' "$VM_JSON" | jq_ "print(json.load(sys.stdin).get('id',''))")"
if [ -n "$VM_ID" ]; then
  echo "linode $VM_LABEL present (id $VM_ID)"
else
  ROOT_PASS="$(openssl rand -base64 30)"   # required by the API; SSH key is the real login. Never printed.
  VM_JSON="$(linode-cli linodes create --label "$VM_LABEL" --region "$REGION" --type "$VM_TYPE" --image "$IMAGE" \
              --root_pass "$ROOT_PASS" --authorized_keys "$(cat "$SSH_PUB")" --firewall_id "$FW_ID" --json \
            | jq_ "print(json.dumps(json.load(sys.stdin)[0]))")"
  unset ROOT_PASS
  VM_ID="$(printf '%s' "$VM_JSON" | jq_ "print(json.load(sys.stdin)['id'])")"
  echo "linode $VM_LABEL created (id $VM_ID, $VM_TYPE, $IMAGE, $REGION)"
fi

# attach the firewall if the instance exists without it
ATTACHED="$(linode-cli firewalls devices-list "$FW_ID" --json | jq_ "print(any(d['entity']['id']==$VM_ID for d in json.load(sys.stdin)))")"
if [ "$ATTACHED" = "True" ]; then
  echo "firewall attached to linode $VM_ID"
else
  linode-cli firewalls device-create "$FW_ID" --id "$VM_ID" --type linode --json >/dev/null
  echo "firewall attached to linode $VM_ID (now)"
fi

# wait for the instance to be running
for _ in $(seq 1 30); do
  STATUS="$(linode-cli linodes view "$VM_ID" --json | jq_ "print(json.load(sys.stdin)[0]['status'])")"
  [ "$STATUS" = "running" ] && break
  sleep 5
done
IPV4="$(linode-cli linodes view "$VM_ID" --json | jq_ "print(json.load(sys.stdin)[0]['ipv4'][0])")"
echo "linode status: $STATUS"

# ---- 3. bucket -----------------------------------------------------------------
BUCKET_JSON="$(api GET /object-storage/buckets | jq_ "print(json.dumps(next((b for b in json.load(sys.stdin)['data'] if b['label']=='$BUCKET'), {})))")"
if [ "$BUCKET_JSON" != "{}" ]; then
  echo "bucket $BUCKET present"
else
  BUCKET_JSON="$(api POST /object-storage/buckets "{\"label\":\"$BUCKET\",\"region\":\"$REGION\"}")"
  echo "bucket $BUCKET created in $REGION"
fi
OBJ_HOST="$(printf '%s' "$BUCKET_JSON" | jq_ "b=json.load(sys.stdin); print(b.get('s3_endpoint') or b.get('hostname','').split('$BUCKET.')[-1])")"
OBJ_REGION_ID="$(printf '%s' "$BUCKET_JSON" | jq_ "b=json.load(sys.stdin); print(b.get('region') or b.get('cluster',''))")"

# ---- 4. limited key ------------------------------------------------------------
KEY_ID="$(api GET /object-storage/keys | jq_ "print(next((k['id'] for k in json.load(sys.stdin)['data'] if k['label']=='$KEY_LABEL'), ''))")"
if [ -n "$KEY_ID" ]; then
  echo "object storage key $KEY_LABEL present (id $KEY_ID); its secret was shown only when it was created"
else
  KEY_JSON="$(api POST /object-storage/keys "{\"label\":\"$KEY_LABEL\",\"bucket_access\":[{\"bucket_name\":\"$BUCKET\",\"permissions\":\"read_write\",\"region\":\"$REGION\"}]}")"
  echo "object storage key $KEY_LABEL created. Put these in .env NOW; the secret is never shown again:"
  printf '%s' "$KEY_JSON" | jq_ "k=json.load(sys.stdin); print('  OBJ_ACCESS_KEY=' + k['access_key']); print('  OBJ_SECRET_KEY=' + k['secret_key'])"
fi

# ---- summary -------------------------------------------------------------------
DASHED="${IPV4//./-}"
cat <<EOF

IPV4=$IPV4
HOST=$DASHED.sslip.io
PUBLIC_BASE_URL=https://$DASHED.sslip.io
MCP_ALLOWED_HOSTS=$DASHED.sslip.io
OBJ_ENDPOINT=https://$OBJ_HOST
OBJ_REGION=$OBJ_REGION_ID
OBJ_BUCKET=$BUCKET
Fallback host if Let's Encrypt refuses sslip.io: $DASHED.ip.linodeusercontent.com (PLAN.md §16.1)
Next: ssh -A root@$IPV4 'bash -s' < scripts/bootstrap_vm.sh
EOF
