#!/usr/bin/env bash
set -euo pipefail

DB="${OKTRADER_DB:-data/oktrader.sqlite}"
OUT_DIR="${OKTRADER_PROFILE_DIR:-data/profiler}"
WALLET="${1:-}"

if [[ -z "$WALLET" ]]; then
  echo "usage: scripts/profile-wallet.sh 0xwallet [db]" >&2
  exit 2
fi

if [[ "${2:-}" != "" ]]; then
  DB="$2"
fi

mkdir -p "$OUT_DIR"
POOL="$OUT_DIR/wallet_pool.txt"
printf '%s\n' "$WALLET" > "$POOL"

echo "[1/5] profile-readiness"
cargo run -- profile-readiness \
  --db "$DB" \
  --wallet-pool "$POOL" \
  --min-trades "${OKTRADER_MIN_TRADES:-5}" \
  --min-markets "${OKTRADER_MIN_MARKETS:-1}" \
  --min-closed-markets "${OKTRADER_MIN_CLOSED_MARKETS:-0}" \
  --min-clob-aligned "${OKTRADER_MIN_CLOB_ALIGNED:-1}" \
  > "$OUT_DIR/readiness.json"

echo "[2/5] export-profiler"
cargo run -- export-profiler \
  --db "$DB" \
  --wallet-pool "$POOL" \
  --out-fills "$OUT_DIR/fills.csv" \
  --out-clob "$OUT_DIR/clob_events.csv"

FILL_ROWS=$(( $(wc -l < "$OUT_DIR/fills.csv") - 1 ))
if [[ "$FILL_ROWS" -le 0 && "${OKTRADER_FETCH_REMOTE_TRADES:-1}" == "1" ]]; then
  echo "[2b/5] local fills empty; fetch-user-trades from Data API"
  PYTHON_BIN="${OKTRADER_PYTHON:-.venv/bin/python}"
  if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
  fi
  "$PYTHON_BIN" profiler/profile_wallets.py fetch-user-trades \
    --wallet "$WALLET" \
    --out "$OUT_DIR/fills.csv" \
    --limit "${OKTRADER_TRADES_LIMIT:-500}" \
    --max-offset "${OKTRADER_TRADES_MAX_OFFSET:-5000}"
fi

echo "[3/5] fetch-gamma-markets"
PYTHON_BIN="${OKTRADER_PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi
"$PYTHON_BIN" profiler/profile_wallets.py fetch-gamma-markets \
  --out "$OUT_DIR/markets.csv" \
  --limit "${OKTRADER_GAMMA_LIMIT:-500}" \
  --max-offset "${OKTRADER_GAMMA_MAX_OFFSET:-5000}"

echo "[4/5] profile"
"$PYTHON_BIN" profiler/profile_wallets.py profile \
  --fills "$OUT_DIR/fills.csv" \
  --clob "$OUT_DIR/clob_events.csv" \
  --markets "$OUT_DIR/markets.csv" \
  --out "$OUT_DIR/rules.json" \
  --factor-out "$OUT_DIR/factor_table.parquet" \
  --strategy-out "$OUT_DIR/strategy_config.json" \
  --report-out "$OUT_DIR/report.md" \
  --html-out "$OUT_DIR/report.html" \
  --diagnostics-out "$OUT_DIR/diagnostics.json" \
  --min-samples "${OKTRADER_MIN_SAMPLES:-2}" \
  --research-engines "${OKTRADER_RESEARCH_ENGINES:-core,alphalens,shap,stumpy,agent}"

echo "[5/5] validate strategy config"
cargo run -- validate-strategy-config --input "$OUT_DIR/strategy_config.json"

echo
echo "outputs:"
echo "  $OUT_DIR/readiness.json"
echo "  $OUT_DIR/diagnostics.json"
echo "  $OUT_DIR/rules.json"
echo "  $OUT_DIR/report.md"
echo "  $OUT_DIR/report.html"
echo "  $OUT_DIR/strategy_config.json"
