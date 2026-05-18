# OKTRADER Implementation Plan

## Product Shape

One Rust CLI project plus one Python research/agent toolbox:

- `collector-data-api`: collects recent public Polymarket trades into SQLite.
- `watch-live`: polls Polygon settlement logs and appends decoded fills.
- `watch-clob`: subscribes to Polymarket CLOB market websocket events for selected asset pools.
- `analyzer`: reads fills from SQLite, computes account metrics, classifies wallets, and maintains the matched smart-money pool.
- `monitor`: reads matched accounts and prints or exports the current key-wallet set.
- `profiler/okprofiler`: mines factor tables, strategy rules, market playbooks, and research reports.
- `scripts/*.py`: portable workflow entrypoints for release builds, VPS runs, wallet profiling, user research, CLOB recording, and agent loops.

The Rust roles stay in one binary for now. If data volume or operations demand
it, these roles can later split into separate services without changing the
database contract. Python remains the research brain and orchestration layer.

## Engineering Rules

- One Rust workspace, one CLI binary, multiple role-based subcommands.
- Keep Rust source files under 300 lines where practical.
- Put shared logic in modules, not in CLI command handlers.
- Keep command orchestration under `src/commands`, CLI/report UX under `src/app`, and chain adapters under `src/chain`.
- Keep strategy research logic under `src/analysis` for Rust and `profiler/okprofiler` for Python.
- SQLite is the local source of truth; JSON/CSV are exports or compatibility paths.
- `PLAN.md` must be updated whenever a milestone changes.
- Portable Python scripts under `scripts/` are the default workflow and overnight run path.
- Shell wrappers have been removed; do not add a second script layer unless a platform truly needs it.
- Research SOP lives in `docs/research_sop.md` and `config/agent_sop.json`.

## Current Status

Implemented:

- deterministic fill model
- closed-loop trade identification
- realized PnL, win rate, expectancy, P/L ratio, maker ratio
- max single-market PnL concentration
- account taxonomy and smart-money tiers
- multi-type matched pool: stable alpha, information edge, stat-arb/market-maker, swing trader, and watchlist tiers
- configurable account type profiles under `config/account_types/*.json`
- manual watchlist import for known smart-money wallets
- Rust analysis modules grouped under `src/analysis`
- Python profiler package split into feature extraction, as-of pipeline, and rule inference
- public Data API collector
- SQLite storage
- analyzer process
- monitor process
- JSON export
- CSV compatibility path
- codebase refactor into small modules under 300 lines
- directory refactor into `app`, `commands`, and `chain`
- portable Python workflow scripts only; legacy shell wrappers removed
- user-to-wallet resolver for Polymarket handles and profile URLs
- end-to-end `research-user` agent path from Polymarket ID to report
- agent SOP status tracking via `sop_status.json`
- human and machine-readable research SOP
- LLM semantic parser hook, disabled by default and enabled only via `OKTRADER_ENABLE_LLM_MARKET_PARSER=1`
- weather-temperature market playbook and weather semantic factors
- Open-Meteo actual weather observation adapter and observation factors

Latest smoke test:

- Command: `python scripts/research_user.py @beefslayer data/oktrader.sqlite --profile-dir data/profiler_smoketest_beefslayer --trades-limit 500 --trades-max-offset 1500 --gamma-limit 200 --gamma-max-offset 800 --min-samples 5`
- Result: passed.
- Resolved wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`.
- Pulled public trade rows: 3020.
- Pulled Gamma market rows: 200.
- Generated: `fills.csv`, `markets.csv`, `factor_table.parquet`, `rules.json`, `research_report.md`, `candidate_factors.json`, `next_commands.json`, `sop_status.json`, and `strategy_config.json`.
- Newer PolyEdge runs also generate `factor_validations.json` and `wallet_clusters.json` when the profiler has enough factor-table input.
- Finding: wallet classified as `weather_temperature` specialist with `weather_market_ratio >= 0.867881`.
- Automatic weather expansion: agent fetched 853 actual observation rows and 41,400 forecast-history rows, then populated actual-temperature and forecast factors.
- Remaining evidence gaps: CLOB snapshots, optional news timeline, model disagreement, and settlement-grade PnL expansion for stronger replication claims.

SQLite tables:

- `fills`: append-only normalized trades
- `wallets`: discovered wallet universe and activity state
- `account_metrics`: latest account feature vectors and classifications
- `matched_accounts`: currently selected smart-money pool
- `scanner_state`: collector/analyzer/live/backfill checkpoints
- `raw_evm_logs`: deduped raw Polygon logs for replay and decoder audits
- `raw_clob_events`: deduped market websocket payload archive
- `clob_asset_features`: latest BBO, spread, depth, OFI, and last-trade microstructure state
- `wallet_microstructure_metrics`: wallet-level fill-to-CLOB timing joins and OFI quality metrics
- `dirty_wallets`: incremental analysis queue
- `market_tokens`: token to market/event metadata mapping
- `markets` / `outcomes`: normalized market context and resolution state
- `positions`: estimated outcome-level open exposure from normalized fills and token metadata
- `wallet_pnl`: estimated wallet PnL from fills plus CLOB mark-to-market when available; settlement-grade audit remains a hardening item
- `wallet_clusters`: future behavioral grouping surface
- `factor_values`: normalized factor observation surface
- `factor_candidates`: factor backlog and lifecycle state
- `factor_validations`: walk-forward / negative-control validation results
- `strategies`: strategy builder outputs and lifecycle state
- `signals`: persisted live strategy triggers

## Command Status

Implemented:

- `init-db`
- `collector-data-api`
- `analyzer`
- `monitor`
- `alerts`
- `import-watchlist`
- `export-profiler`
- `profile-readiness`
- `validate-strategy-config`
- `research-status`
- `build-wallet-intelligence`
- `summary`
- `export`
- `sync-metadata`
- `scan-data-api`
- `analyze-csv`
- `list-taxonomy`
- `watch-live`
- `watch-clob`
- `build-microstructure`

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
   - [x] Add CLOB order-book feature extraction for BBO, spread, book depth, OFI, and last trade state.
   - [x] Add wallet-level fill-to-CLOB timing joins for spread, OFI, and favorable flow rate.
   - [x] Feed wallet microstructure metrics into analyzer reports and monitor/export JSON.
   - [ ] Use wallet microstructure metrics as secondary classification and alert signals.
   - [ ] Add address-level maker behavior joins where wallet attribution is available from settlement logs.

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
   - Status: implemented for alerting and config validation; expanding reconstruction depth.
   - [x] Emit new-fill alerts for matched wallets, with optional all-wallet debug mode.
   - [x] Emit watchlist-only alerts for manually supplied smart-money addresses.
   - [x] Add webhook delivery for alert messages.
   - [x] Store alert cursor in `scanner_state`.
   - [x] Add release/VPS background run Python scripts with logs, pid files, status, and stop commands.
   - [x] Add first wallet-level microstructure joins: spread at fill, OFI at fill, favorable OFI rate.
   - [x] Default matched pool tracks multiple smart-money account types, not only the strict stable-alpha funnel.
   - [x] Add summary command for full tier/tag distribution across all analyzed wallets.
   - [x] Move account type judgment rules into configurable profile files.
   - [x] Add strategy reconstruction features: market breadth, time-of-day, same-market reentry, weather specialization, and weather bucket semantics.
   - [x] Add estimated wallet positions and wallet PnL rebuilt from fills.
   - [x] Persist Gamma markets/outcomes alongside token metadata.
   - [x] Resolve positions to outcome-level token IDs and mark open exposure from latest CLOB BBO mid.
   - [x] Persist validated strategy definitions into `strategies`.
   - [x] Persist live strategy trigger events into `signals`.
   - [x] Add first-pass heuristic wallet clustering persisted into `wallet_clusters`.
   - [ ] Add strategy reconstruction features: entry-before-move, exit quality, sector-specific PnL, and stronger lead-time evidence.
   - [ ] Harden wallet PnL with settlement/redemption events.

5. Python Profiler
   - Status: core reverse-engineering loop implemented; expanding factor library.
   - [x] Add reverse-engineering readiness gate for known wallets.
   - [x] Export known-wallet fills and raw CLOB events for profiler input.
   - [x] Add Python Polars as-of join from fills to previous CLOB events.
   - [x] Split profiler into package modules: CLI, features, pipeline, rules.
   - [x] Extract spread and OFI features for reverse engineering.
   - [x] Extract depth imbalance, price momentum, and time-to-resolution features.
   - [x] Add KDE/quantile threshold output to `rules.json`.
   - [x] Add optional external news timeline as-of ingestion.
   - [x] Export `factor_table.parquet` for iterative ML/research workflows.
   - [x] Export `strategy_config.json` for Rust monitor ingestion.
   - [x] Add Rust strategy config validator.
   - [x] Feed profiler strategy triggers into live Rust alert evaluation.
   - [x] Add profiler success score: reproducibility, coverage, precision, and factor stability.
   - [x] Add profiler Markdown/HTML report and agent-style research notes.
   - [x] Split profiler into factor registry, miner, researcher, and live strategy exporter.
   - [x] Add automatic single-factor and pair-factor search with best offline/live rules.
   - [x] Add research matrix adapters for core, Alphalens-like IC, SHAP-like feature importance, STUMPY-like motifs, Nautilus replay manifest, and agent suggestions.
   - [x] Turn `features/` and `research/` into real Python packages with concrete modules.
   - [x] Add profiler diagnostics output for missing source/factor coverage.
   - [x] Add Gamma market metadata fetcher for `markets.csv`.
   - [x] Add RSS news fetcher for optional `news.csv` event timeline input.
   - [x] Add one-wallet end-to-end profiling script from address to report/config.
   - [x] Add Data API wallet trade fetch fallback when local DB has no fills.
   - [x] Add maintained factor catalog plus per-run factor summary and research log.
   - [x] Generate CLOB asset pools from wallet fills and add wallet CLOB recording script.
   - [x] Add Polymarket user/profile URL resolver.
   - [x] Add end-to-end `research-user` flow from ID to wallet, data fetch, profiler, agent report, and next commands.
   - [x] Add portable Python workflow scripts and remove legacy shell wrappers.
   - [x] Add agent SOP status tracking with `sop_status.json`.
   - [x] Add weather market category playbook and weather semantic/observation factors.
   - [x] Add Open-Meteo historical forecast adapter.
   - [x] Add forecast factors: `forecast_temp_f`, `forecast_error_to_bucket`, `forecast_inside_bucket`, `forecast_delta_1h`, `forecast_delta_6h`, and `forecast_volatility`.
   - [x] Add LLM semantic parser hook behind explicit opt-in.
   - [x] Add first-pass factor validation output with walk-forward, negative-control lift, and stability scoring.
   - [x] Persist agent candidate factors and validation rows into SQLite lifecycle tables.
   - [x] Advance factor candidate lifecycle from validation verdicts, including decayed factors.
   - [ ] Add true negative-set backtests across non-wallet fills for real precision/recall.
   - [ ] Replace lightweight adapters with full optional Qlib/Alphalens/STUMPY/SHAP/Nautilus integrations when data format and dependencies are ready.
   - [ ] Add multi-model forecast adapter for `model_disagreement`.
   - [ ] Add richer factor library: market sector PnL, pre-news lead time, exit quality, and negative-control precision/recall.

6. Production storage option
   - Status: planned.
   - Keep SQLite as local default.
   - Add Postgres for wallet/config state.
   - Add ClickHouse for large tick/order-book and historical log analytics.
