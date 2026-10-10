#!/usr/bin/env bash
# One-time VM setup (PLAN.md §16.1 step 4). Run from the laptop with agent forwarding so the
# private repo clones with your GitHub key:   ssh -A root@<IP> 'bash -s' < scripts/bootstrap_vm.sh
# Idempotent: safe to re-run.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
REPO="${REPO:-git@github.com:yephrem22/callmeback.git}"
DEST=/opt/callmeback

apt-get update -q
apt-get -y -q upgrade
apt-get -y -q install git sqlite3 curl ca-certificates
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null

mkdir -p ~/.ssh && chmod 700 ~/.ssh
grep -q github.com ~/.ssh/known_hosts 2>/dev/null || ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null

if [ -d "$DEST/.git" ]; then
  echo "repo present at $DEST"
else
  git clone "$REPO" "$DEST"
fi
git config --global --add safe.directory "$DEST" || true
mkdir -p "$DEST/data" "$DEST/eb_data"
chmod 700 "$DEST"

echo "docker: $(docker --version)"
echo "compose: $(docker compose version)"
echo "repo at $DEST on $(git -C "$DEST" rev-parse --short HEAD)"
echo "next: copy .env (PLAN.md §16.1), edit HOST/PUBLIC_BASE_URL/MCP_ALLOWED_HOSTS/ACME_EMAIL, then docker compose up -d --build"
