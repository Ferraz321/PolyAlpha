#!/usr/bin/env bash
set -euo pipefail

USER_ID="${1:-}"
if [[ -z "$USER_ID" ]]; then
  echo "usage: scripts/research-user.sh @username-or-url [db]" >&2
  exit 2
fi

DB="${2:-${OKTRADER_DB:-data/oktrader.sqlite}}"
PYTHON_BIN="${OKTRADER_PYTHON:-.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" profiler/profile_wallets.py research-user \
  "$USER_ID" \
  --db "$DB" \
  --update-candidates
