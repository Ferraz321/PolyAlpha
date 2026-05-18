# OKTRADER Implementation Plan

## Product Shape

One Rust CLI project with three long-running roles:

- `collector-data-api`: collects recent public Polymarket trades into SQLite.
- `analyzer`: reads fills from SQLite, computes account metrics, classifies wallets, and maintains the matched smart-money pool.
- `monitor`: reads matched accounts and prints or exports the current key-wallet set.

The project keeps all roles in one binary for now. If data volume or operations demand it, these roles can later split into separate services without changing the database contract.

## Current Milestone

Implemented:

- deterministic fill model
- closed-loop trade identification
- realized PnL, win rate, expectancy, P/L ratio, maker ratio
- max single-market PnL concentration
- account taxonomy and smart-money tiers
- public Data API collector
- SQLite storage
- analyzer process
- monitor process
- JSON export
- CSV compatibility path

SQLite tables:

- `fills`: append-only normalized trades
- `wallets`: discovered wallet universe and activity state
- `account_metrics`: latest account feature vectors and classifications
- `matched_accounts`: currently selected smart-money pool
- `scanner_state`: reserved for collector/analyzer checkpoints

## Next Milestones

1. Polygon historical backfill
   - Add CTFExchange `OrderFilled` ABI decoding.
   - Batch `eth_getLogs` by block range.
   - Persist decoded fills into SQLite with the same dedupe key.
   - Store backfill checkpoint in `scanner_state`.

2. Live collector
   - Subscribe to Polygon new blocks or poll recent block ranges.
   - Add Polymarket CLOB websocket trade/book ingestion.
   - Merge live events through the same storage boundary.

3. Incremental analysis
   - Track dirty wallets from newly inserted fills.
   - Recompute only changed wallets instead of the full database.
   - Add wallet lifecycle states: `cold`, `active`, `watchlist`, `matched`, `excluded`.

4. Monitoring and strategy research
   - Emit smart-money trade alerts.
   - Store wallet watch events.
   - Add strategy reconstruction features: lead time, market breadth, sector concentration, entry-before-move, exit quality.

5. Production storage option
   - Keep SQLite as local default.
   - Add Postgres for wallet/config state.
   - Add ClickHouse for large tick/order-book and historical log analytics.
