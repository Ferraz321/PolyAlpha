# OKTRADER Implementation Plan

## Product Shape

One Rust CLI project with three long-running roles:

- `collector-data-api`: collects recent public Polymarket trades into SQLite.
- `watch-live`: polls Polygon settlement logs and appends decoded fills.
- `watch-clob`: subscribes to Polymarket CLOB market websocket events for selected asset pools.
- `analyzer`: reads fills from SQLite, computes account metrics, classifies wallets, and maintains the matched smart-money pool.
- `monitor`: reads matched accounts and prints or exports the current key-wallet set.

The project keeps all roles in one binary for now. If data volume or operations demand it, these roles can later split into separate services without changing the database contract.

## Engineering Rules

- One Rust workspace, one CLI binary, multiple role-based subcommands.
- Keep Rust source files under 300 lines where practical.
- Put shared logic in modules, not in CLI command handlers.
- Keep command orchestration under `src/commands`, CLI/report UX under `src/app`, and chain adapters under `src/chain`.
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
- directory refactor into `app`, `commands`, and `chain`

SQLite tables:

- `fills`: append-only normalized trades
- `wallets`: discovered wallet universe and activity state
- `account_metrics`: latest account feature vectors and classifications
- `matched_accounts`: currently selected smart-money pool
- `scanner_state`: collector/analyzer/live/backfill checkpoints
- `raw_evm_logs`: deduped raw Polygon logs for replay and decoder audits
- `raw_clob_events`: deduped market websocket payload archive
- `dirty_wallets`: incremental analysis queue
- `market_tokens`: token to market/event metadata mapping

## Command Status

Implemented:

- `init-db`
- `collector-data-api`
- `analyzer`
- `monitor`
- `export`
- `sync-metadata`
- `scan-data-api`
- `analyze-csv`
- `list-taxonomy`
- `watch-live`
- `watch-clob`

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
   - [x] Persist raw EVM logs into `raw_evm_logs`.
   - [x] Add configurable multiple exchange addresses.
   - [x] Add Neg Risk CTF Exchange support flag.
   - [x] Add CTF Exchange V2 event decoder.
   - [x] Add taker-side reconstruction for direct fills where the taker is a real wallet.
   - [x] Add robust handling for Exchange-as-taker multi-order matches.
   - [x] Add market metadata mapping for token ID to condition/event slug.
   - [x] Add integration test fixture for historical-log-shaped V2 `OrderFilled`.

2. Live collector
   - Status: partial implementation.
   - [x] Add live CLI args for RPC URL, exchange set, polling cadence, and lookback window.
   - [x] Poll Polygon latest block by JSON-RPC.
   - [x] Maintain `watch_live.next_block` and `watch_live.last_block` scanner state.
   - [x] Reuse V1/V2 `OrderFilled` decoder from historical backfill.
   - [x] Persist raw live EVM logs into `raw_evm_logs`.
   - [x] Merge live decoded fills through the same SQLite storage boundary.
   - [x] Mark newly touched wallets dirty for incremental analyzer refresh.
   - [x] Add Polymarket CLOB market websocket subscription by asset token pool.
   - [x] Add market websocket `PING` heartbeat.
   - [x] Persist raw CLOB book/price/trade payloads into `raw_clob_events`.
   - [x] Add websocket reconnect and exponential backoff handling.
   - [ ] Add CLOB order-book feature extraction for OFI, maker behavior, and BBO placement.

3. Incremental analysis
   - Status: partial implementation.
   - [x] Add `dirty_wallets` queue table.
   - [x] Mark wallets dirty when new fills are inserted.
   - [x] Analyzer consumes and clears dirty wallet queue.
   - [x] Add wallet lifecycle states: `cold`, `active`, `watchlist`, `matched`, `excluded`.
   - [x] Update lifecycle status for matched and stale wallets.
   - [x] Recompute only changed wallets instead of full database.
   - [x] Add per-wallet fill loading for efficient partial recompute.
   - [x] Preserve previous metrics for non-dirty wallets during incremental cycles.

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
