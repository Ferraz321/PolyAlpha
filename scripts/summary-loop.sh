#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/runtime-env.sh
BIN="./target/release/oktrader-alpha"

while true; do
  date -Is
  "$BIN" summary --db "$OKTRADER_DB"
  sleep "$SUMMARY_INTERVAL_SECS"
done
