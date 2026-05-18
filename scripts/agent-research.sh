#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${OKTRADER_PROFILE_DIR:-data/profiler}"
PYTHON_BIN="${OKTRADER_PYTHON:-.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" profiler/profile_wallets.py agent \
  --profile-dir "$OUT_DIR" \
  "$@"
