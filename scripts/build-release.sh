#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data logs run
cargo build --release
./target/release/oktrader-alpha init-db --db "${OKTRADER_DB:-data/oktrader.sqlite}"
echo "release binary ready: target/release/oktrader-alpha"
