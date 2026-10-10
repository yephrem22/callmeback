#!/usr/bin/env bash
# Redeploy the current main on the VM (PLAN.md §16.2). Run on the VM: cd /opt/callmeback && bash scripts/deploy.sh
set -euo pipefail
start=$(date +%s)
cd /opt/callmeback
git pull --ff-only
docker compose up -d --build
docker compose ps
echo "deploy finished in $(( $(date +%s) - start )) s at commit $(git rev-parse --short HEAD)"
