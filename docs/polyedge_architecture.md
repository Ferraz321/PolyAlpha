# PolyEdge Alpha Research Agent Architecture

PolyEdge upgrades the project from a scanner plus profiler into an Alpha
Research Agent platform.

The central product line is:

```text
smart wallets
  -> why they make money
  -> which behaviors are reusable
  -> which factors survive validation
  -> which strategies should emit live signals
```

## Layer Model

```text
External Data
  Polymarket Data API / Gamma / Polygon RPC / CLOB WS
  Weather / News / Forecasts / Settlement / Social signals
        |
        v
Data Layer
  ingestion, normalization, dedupe, source health
        |
        v
Unified Storage
  SQLite local first, later Postgres + ClickHouse
        |
        v
Wallet Intelligence Layer
  estimated PnL, positions, wallet metrics, clustering, risk tags
        |
        v
Strategy Reverse Engineering Layer
  behavior profile, timing, market category, entry/exit logic
        |
        v
Factor Research Layer
  factor table, factor registry, candidate factors, feature adapters
        |
        v
Validation Layer
  walk-forward, negative set, stability, slippage, capacity, decay
        |
        v
Strategy Signal Layer
  validated factors, strategy configs, scoring, risk limits, signals
        |
        v
Agent Orchestration Layer
  missing-data detection, next commands, reports, lifecycle promotion
```

## Engine Split

Rust remains the reliable execution engine:

- long-running collectors
- SQLite writes and schema ownership
- Polygon/CLOB ingestion
- alerting and live strategy checks
- strategy config validation
- operational CLI commands

Python remains the research intelligence engine:

- profiler and factor table creation
- strategy reverse engineering
- wallet clustering
- factor validation
- report generation
- agent planning and lifecycle promotion

## Storage Contract

Existing tables remain valid. The platform adds lifecycle-oriented tables:

- `markets`, `outcomes`: normalized market context and resolution state
- `positions`, `wallet_pnl`: estimated wallet exposure and PnL surfaces from
  fills today; settlement/redemption-grade audit is a future hardening step
- `wallet_clusters`: behavioral grouping
- `factor_values`: normalized factor observations
- `factor_candidates`: factor backlog and lifecycle state
- `factor_validations`: anti-overfit evidence and verdicts
- `strategies`: strategy builder outputs
- `signals`: live and simulated strategy emissions

SQLite is still the local source of truth. Postgres can later own wallet/config
state, and ClickHouse can own high-volume CLOB/order-book history without
changing the research contract.

## Module Ownership

```text
src/
  commands/              Rust CLI orchestration
  chain/                 Polygon/RPC adapters
  analysis/              wallet metrics, tagging, microstructure
  storage*.rs            SQLite boundaries
  strategy_config.rs     live signal rule validation

profiler/okprofiler/     current production Python research engine
profiler/polyedge/       next platform namespace
  features/              source-to-feature adapters
  factors/               candidate factor lifecycle
  validation/            walk-forward and negative-control results
  clustering/            wallet behavior grouping
  reverse_engineering/   behavior profiles and strategy hypotheses
  agent/                 orchestration facade
```

## Factor Lifecycle

```text
candidate
  -> researching
  -> validating
  -> approved / rejected
  -> live
  -> decayed
```

Promotion gates:

- factor has an owner module
- required data sources are explicit
- factor has non-null rows in a factor table
- factor has in-sample and out-of-sample evidence
- factor survives negative-control checks
- slippage and capacity are estimated
- live/offline status is explicit
- decay monitoring exists before strategy promotion

## Implementation Priorities

1. Harden data identity:
   improve fill dedupe keys, CLOB event indexing, and settlement-grade PnL.

2. Build wallet intelligence:
   estimated positions, wallet PnL, clustering, and risk labels; then harden
   PnL with settlement/redemption evidence.

3. Formalize reverse engineering:
   entry/exit hypotheses, category playbooks, timing profiles, and repeated
   behavior motifs.

4. Promote factor lifecycle:
   write candidates and validations to storage, then generate strategy configs
   only from approved factors.

5. Close the agent loop:
   diagnostics should decide the next data collection and validation commands,
   then update reports and lifecycle states.

## Current Implementation Surface

- `cargo run -- research-status` reports counts for wallet intelligence, factor
  lifecycle, strategy, and signal tables.
- `cargo run -- build-wallet-intelligence` rebuilds estimated positions and
  wallet PnL from normalized fills.
- `cargo run -- sync-metadata` persists Gamma market context into `markets`,
  `outcomes`, and `market_tokens`.
- Wallet intelligence uses token metadata for outcome-level positions and
  latest CLOB BBO mid prices for mark-to-market unrealized PnL when available.
- Reverse engineering factors now include directional entry-before-move
  evidence, exit-quality proxies, sector concentration, news recency, resolution
  lead time, and repeated entry motifs.
- `profiler/okprofiler/validation.py` runs a first validation pass using
  walk-forward splits, negative-control lift, and factor stability.
- `profile_wallets.py profile` writes `factor_validations.json`.
- `profile_wallets.py profile` writes `wallet_clusters.json` using a first-pass
  behavior clustering heuristic with wallet rhythm, sector, entry-edge, and
  exit-quality features.
- Agent runs persist validation rows into `factor_validations`.
- Agent runs persist behavior clusters into `wallet_clusters`.
- Validation persistence advances `factor_candidates` lifecycle state to
  `validating`, `approved`, `rejected`, or `decayed`.
- `strategy_config.json` is now gated by approved live factors instead of every
  explainable live rule.
- `validate-strategy-config --db ...` persists strategy lifecycle rows.
- `alerts --strategy-config ...` persists live trigger rows into `signals`.
