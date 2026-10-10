#!/usr/bin/env bash
# Consistent SQLite backup while the app keeps running (PLAN.md §16.2). Run from the repo root on the VM.
set -euo pipefail
src="${1:-data/app.db}"
dst="data/app.$(date +%H%M).db"
sqlite3 "$src" ".backup $dst"
echo "backup written: $dst ($(du -h "$dst" | cut -f1))"
