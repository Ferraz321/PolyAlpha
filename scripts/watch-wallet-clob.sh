#!/usr/bin/env bash
set -euo pipefail

WALLET="${1:-}"
DB="${2:-${OKTRADER_DB:-data/oktrader.sqlite}}"
OUT_DIR="${OKTRADER_PROFILE_DIR:-data/profiler_wallet_clob}"

if [[ -z "$WALLET" ]]; then
  echo "usage: scripts/watch-wallet-clob.sh 0xwallet [db]" >&2
  exit 2
fi

mkdir -p "$OUT_DIR"

OKTRADER_PROFILE_DIR="$OUT_DIR" scripts/profile-wallet.sh "$WALLET" "$DB"

echo
echo "starting CLOB recorder for assets in $OUT_DIR/clob_assets.txt"
echo "leave this running, then rerun scripts/profile-wallet.sh after enough events accumulate"

cargo run -- watch-clob \
  --db "$DB" \
  --assets-file "$OUT_DIR/clob_assets.txt" \
  --chunk-size "${OKTRADER_CLOB_CHUNK_SIZE:-500}" \
  --reconnect-min-secs "${OKTRADER_CLOB_RECONNECT_MIN_SECS:-2}" \
  --reconnect-max-secs "${OKTRADER_CLOB_RECONNECT_MAX_SECS:-60}"
