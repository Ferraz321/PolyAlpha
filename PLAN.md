# OKTRADER Implementation Plan

## Product Shape

One Rust CLI project with three long-running roles:

- `collector-data-api`: collects recent public Polymarket trades into SQLite.
- `analyzer`: reads fills from SQLite, computes account metrics, classifies wallets, and maintains the matched smart-money pool.
- `monitor`: reads matched accounts and prints or exports the current key-wallet set.

The project keeps all roles in one binary for now. If data volume or operations demand it, these roles can later split into separate services without changing the database contract.

## Engineering Rules

- One Rust workspace, one CLI binary, multiple role-based subcommands.
- Keep Rust source files under 300 lines where practical.
- Put shared logic in modules, not in CLI command handlers.
- SQLite is the local source of truth; JSON/CSV are exports or compatibility paths.
- `PLAN.md` must be updated whenever a milestone changes.

## Current Status

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
- codebase refactor into small modules under 300 lines

SQLite tables:

- `fills`: append-only normalized trades
- `wallets`: discovered wallet universe and activity state
- `account_metrics`: latest account feature vectors and classifications
- `matched_accounts`: currently selected smart-money pool
- `scanner_state`: reserved for collector/analyzer checkpoints

## Command Status

Implemented:

- `init-db`
- `collector-data-api`
- `analyzer`
- `monitor`
- `export`
- `scan-data-api`
- `analyze-csv`
- `list-taxonomy`

Interface reserved, implementation pending:

- `watch-live`

Partially implemented:

- `backfill-polygon`

## Next Milestones

1. Polygon historical backfill
   - Status: partial implementation.
   - [x] Add CLI args for RPC URL, CTF Exchange address, block range, and batch size.
   - [x] Add JSON-RPC client for `eth_blockNumber`, `eth_getBlockByNumber`, and `eth_getLogs`.
   - [x] Add standard V1 `OrderFilled` event topic generation.
   - [x] Batch `eth_getLogs` by block range.
   - [x] Decode maker-side standard `OrderFilled` logs into normalized fills.
   - [x] Persist decoded fills into SQLite with the same dedupe key.
   - [x] Store backfill checkpoint in `scanner_state`.
   - [ ] Persist raw EVM logs into `raw_evm_logs`.
   - [ ] Add Neg Risk CTF Exchange support.
   - [ ] Add CTF Exchange V2 event decoder.
   - [ ] Add taker-side reconstruction for direct fills where the taker is a real wallet.
   - [ ] Add robust handling for Exchange-as-taker multi-order matches.
   - [ ] Add market metadata mapping for token ID to condition/event slug.
   - [ ] Add integration test with a known historical transaction/log fixture.

2. Live collector
   - Status: pending implementation.
   - Subscribe to Polygon new blocks or poll recent block ranges.
   - Add Polymarket CLOB websocket trade/book ingestion.
   - Merge live events through the same storage boundary.

3. Incremental analysis
   - Status: pending implementation.
   - Track dirty wallets from newly inserted fills.
   - Recompute only changed wallets instead of the full database.
   - Add wallet lifecycle states: `cold`, `active`, `watchlist`, `matched`, `excluded`.

4. Monitoring and strategy research
   - Status: pending implementation.
   - Emit smart-money trade alerts.
   - Store wallet watch events.
   - Add strategy reconstruction features: lead time, market breadth, sector concentration, entry-before-move, exit quality.

5. Production storage option
   - Status: planned.
   - Keep SQLite as local default.
   - Add Postgres for wallet/config state.
   - Add ClickHouse for large tick/order-book and historical log analytics.
