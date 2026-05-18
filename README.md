# OKTRADER Alpha

Rust toolkit for cross-market Polymarket smart-money mining.

The project is a single Rust CLI with three production roles:

- `collector-data-api`: continuously collects recent public Polymarket trades.
- `watch-live`: continuously polls Polygon settlement logs for verified fills.
- `watch-clob`: continuously archives selected CLOB market websocket events.
- `analyzer`: continuously computes wallet features and account classifications.
- `monitor`: continuously watches the classified smart-money pool.

SQLite is the default local database at `data/oktrader.sqlite`; JSON/CSV files are exports and compatibility paths, not the long-term primary store.

## Quick Start

```bash
cargo run -- init-db --db data/oktrader.sqlite

cargo run -- collector-data-api \
  --db data/oktrader.sqlite \
  --interval-secs 30

cargo run -- analyzer \
  --db data/oktrader.sqlite \
  --tier candidate-smart-money \
  --tier core-smart-money \
  --tag stable-alpha-wallet \
  --tag information-edge-wallet \
  --interval-secs 60

cargo run -- monitor --db data/oktrader.sqlite --interval-secs 10
```

Polygon settlement live scanner:

```bash
cargo run -- watch-live \
  --db data/oktrader.sqlite \
  --rpc-url "$POLYGON_RPC_URL" \
  --include-neg-risk
```

CLOB microstructure scanner for a token pool:

```bash
cargo run -- watch-clob \
  --db data/oktrader.sqlite \
  --assets-file data/clob_assets.txt \
  --reconnect-min-secs 2 \
  --reconnect-max-secs 60
```

One-shot local smoke test:

```bash
cargo run -- init-db --db data/oktrader.sqlite
cargo run -- collector-data-api --db data/oktrader.sqlite --once --page-size 100 --max-offset 0
cargo run -- analyzer --db data/oktrader.sqlite --once --tag small-sample-noise
cargo run -- monitor --db data/oktrader.sqlite --once
```

## Core Engine

The implementation focuses on the deterministic quant core:

- normalized fill event model
- closed-loop trade identification
- realized PnL, win rate, profit/loss ratio, expectancy, maker ratio
- max single-market PnL concentration for excluding one-shot lucky wallets
- capacity, statistical significance, and alpha-generation funnel
- rule-based account taxonomy for stable alpha wallets, information-edge wallets, market-maker bots, swing traders, one-shot whales, and noise

## Project Layout

```text
src/app/          CLI args, report filtering, taxonomy text
src/commands/     command implementations: collector, analyzer, backfill, websocket, metadata, CSV compatibility
src/chain/        EVM JSON-RPC adapter
src/*.rs          reusable core library modules: model, metrics, storage, tagging, ingestion
sql/schema.sql    SQLite schema
tests/fixtures/   historical-log-shaped decoder fixtures
```

## CSV Input

`analyze-csv` expects normalized fill rows:

```csv
account,market_id,condition_id,event_slug,sector,side,role,price,shares,timestamp,tx_hash,order_hash
0xabc,m1,,election-2026,politics,buy,taker,0.40,1000,2026-01-01T00:00:00Z,,
0xabc,m1,,election-2026,politics,sell,taker,0.62,950,2026-01-02T00:00:00Z,,
```

`side` is `buy` or `sell`; `role` is `maker` or `taker`.

## Run

```bash
cargo run -- analyze-csv --input fills.csv
```

Only show accounts passing the smart-money funnel:

```bash
cargo run -- analyze-csv --input fills.csv --passed-only
```

## Continuous Public Scanner

This mode pulls public Polymarket Data API trades, appends normalized fills, and refreshes an account report after every cycle:

```bash
cargo run -- scan-data-api
```

Useful variants:

```bash
cargo run -- scan-data-api --once
cargo run -- scan-data-api --passed-only
cargo run -- scan-data-api --interval-secs 30 --page-size 1000 --max-offset 10000
```

Outputs:

- `data/fills.csv`: normalized trade ledger
- `data/account_reports.json`: account feature vectors, funnel decisions, and tags
- `data/matched_accounts.json`: filtered accounts matching requested tiers/tags/wallet pool
- `data/scanner_stats.json`: scan counters, wallet counts, and matched account count

This scanner uses the public Data API (`https://data-api.polymarket.com/trades`). It is good for continuous discovery. A production-grade build should still add Polygon log replay for settlement-level verification.

`scan-data-api` is the older CSV-compatible scanner. Prefer `collector-data-api` + `analyzer` for ongoing work.

`watch-clob` uses Polymarket's public market websocket. It archives raw book, price, and trade payloads for token IDs listed one per line in `--assets-file`, and maintains `clob_asset_features` with BBO, spread, depth, OFI, and last-trade state. Public CLOB market messages do not identify wallet addresses, so wallet attribution still comes from Polygon settlement logs.

## CLI Workflow

Show supported smart-money tiers and account types:

```bash
cargo run -- list-taxonomy
```

Continuously scan and output only stable alpha / information-edge candidates:

```bash
cargo run -- scan-data-api \
  --tier candidate-smart-money \
  --tier core-smart-money \
  --tag stable-alpha-wallet \
  --tag information-edge-wallet \
  --interval-secs 30
```

Scan only a known wallet pool:

```bash
cargo run -- scan-data-api --wallet-pool wallets.txt
```

`wallets.txt` format:

```text
0xabc...
0xdef...
```

Filter an existing ledger without calling the network:

```bash
cargo run -- analyze-csv --input data/fills.csv --tag stat-arb-market-maker-bot
cargo run -- analyze-csv --input data/fills.csv --tier watchlist
```

The intended production shape is:

```text
collector-data-api public trade radar for recent/new wallets
analyzer           account scoring and classification process
monitor            matched smart-money wallet monitor
export             export matched accounts from SQLite
backfill-polygon   planned historical full wallet universe from OrderFilled logs
watch-live         planned real-time Polygon/CLOB listener
analyze-csv        offline replay and research compatibility path
list-taxonomy      supported account and bot types
```

## Default Funnel

- total volume > 50,000
- average trade size > 1,000
- closed markets >= 15
- total realized PnL > 10,000
- win rate >= 75%

## Account Taxonomy

The scanner separates account types instead of treating every profitable wallet as smart money:

- `stable_alpha_wallet`: enough trades, enough closed markets, positive realized PnL, good win rate, good profit/loss ratio, and no single-market over-concentration.
- `information_edge_wallet`: lower frequency, high win rate, positive PnL, and concentrated timing/sector behavior.
- `stat_arb_market_maker_bot`: high trade count, many markets, high maker ratio, moderate win rate, stable small-edge PnL.
- `swing_trader`: moderate win rate with high profit/loss ratio.
- `one_shot_whale`: profitable but too much PnL from one market.
- `small_sample_noise`: not enough trades or closed markets.
- `high_volume_noise`: large volume without positive realized edge.

## Next Engineering Layer

Recommended production architecture:

- CLOB WebSocket collector: Polymarket L2 book and trades, persisted as tick-level events.
- EVM log collector: Polygon `CTFExchange::OrderFilled` and ConditionalTokens ERC-1155 transfers.
- Metadata resolver: Gamma API condition and market-asset mapping.
- Stream bus: Redpanda/Kafka topics for `raw.clob`, `raw.evm`, `normalized.fills`, `features.account`.
- Storage: ClickHouse for tick analytics, Postgres for metadata/config, object storage for immutable raw archives.
- Feature jobs: Rust stream processors for near-real-time feature vectors plus replayable batch recomputation.
