#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
source scripts/runtime-env.sh
mkdir -p data logs run

BIN="./target/release/oktrader-alpha"
if [[ ! -x "$BIN" ]]; then
  cargo build --release
fi

"$BIN" init-db --db "$OKTRADER_DB"

start_role() {
  local name="$1"
  shift
  if [[ -f "run/$name.pid" ]] && kill -0 "$(cat "run/$name.pid")" 2>/dev/null; then
    echo "$name already running pid=$(cat "run/$name.pid")"
    return
  fi
  nohup "$BIN" "$@" >> "logs/$name.log" 2>&1 &
  echo "$!" > "run/$name.pid"
  echo "started $name pid=$!"
}

start_script() {
  local name="$1"
  shift
  if [[ -f "run/$name.pid" ]] && kill -0 "$(cat "run/$name.pid")" 2>/dev/null; then
    echo "$name already running pid=$(cat "run/$name.pid")"
    return
  fi
  nohup "$@" >> "logs/$name.log" 2>&1 &
  echo "$!" > "run/$name.pid"
  echo "started $name pid=$!"
}

start_role collector collector-data-api \
  --db "$OKTRADER_DB" \
  --interval-secs "$COLLECTOR_INTERVAL_SECS"

start_role analyzer analyzer \
  --db "$OKTRADER_DB" \
  --interval-secs "$ANALYZER_INTERVAL_SECS"

start_role alerts alerts \
  --db "$OKTRADER_DB" \
  --interval-secs "$ALERT_INTERVAL_SECS" \
  --all-wallets

start_script summary-loop scripts/summary-loop.sh

if [[ "$OKTRADER_ENABLE_RPC" == "1" ]]; then
  if [[ -z "$POLYGON_RPC_URL" ]]; then
    echo "OKTRADER_ENABLE_RPC=1 but POLYGON_RPC_URL is empty" >&2
    exit 1
  fi
  start_role watch-live watch-live \
    --db "$OKTRADER_DB" \
    --rpc-url "$POLYGON_RPC_URL" \
    --include-neg-risk
else
  echo "watch-live skipped; set OKTRADER_ENABLE_RPC=1 and POLYGON_RPC_URL to enable"
fi

scripts/status.sh
