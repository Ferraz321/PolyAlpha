# OKTRADER Research SOP

This SOP turns wallet research into a repeatable loop: collect data, mine
factors, write evidence, propose new factors, and promote reusable findings
back into the codebase.

The machine-readable version is `config/agent_sop.json`. The Agent CLI writes
`sop_status.json` on every run so the current profile directory always shows
which stages are complete and which data gaps remain.

## Standard Entry Point

```bash
python scripts/research_user.py @beefslayer data/oktrader.sqlite
```

The input can be a Polymarket handle, profile URL, or wallet address depending
on the command path. The standard profile directory is `data/profiler_<handle>`.

## Stage 1: Identity

Goal: resolve the human identifier into a wallet pool.

Tools:

- `resolve-user`
- `wallet_pool.txt`

Outputs:

- `resolved_user.json`
- `wallet_pool.txt`

Pass condition: the research run has at least one wallet address.

## Stage 2: Data Ingestion

Goal: build the minimum research table for the wallet.

Tools:

- Rust `profile-readiness`
- Rust `export-profiler`
- Python `fetch-user-trades` fallback
- Python `fetch-gamma-markets`

Outputs:

- `fills.csv`
- `markets.csv`
- optional `clob_events.csv`
- optional `weather_observations.csv`

Pass condition: `diagnostics.json` marks fills and market metadata as ready.

## Stage 3: Readiness Gate

Goal: decide whether the data can support a real reverse-engineering claim.

Outputs:

- `readiness.json`
- `diagnostics.json`

Rules:

- If fills are too sparse, the report may only describe behavior.
- If CLOB is missing, OFI, spread, depth imbalance, and momentum claims are
  not considered proven.
- If weather observations or forecasts are missing, weather accounts can be
  classified but not fully replicated.

## Stage 4: Factor Mining

Goal: generate the evidence table and extract candidate rules.

Tools:

- `profiler/okprofiler/features/*`
- `miner.py`
- `research_matrix.py`

Outputs:

- `factor_table.parquet`
- `factor_summary.md`
- `rules.json`
- `strategy_config.json`

Every active factor must be registered in
`profiler/okprofiler/features/registry.py` and documented in
`docs/factors.md`.

## Stage 5: Market Playbook

Goal: classify the wallet into reusable strategy categories.

Examples:

- stable alpha wallet
- information edge wallet
- stat-arb / market maker
- swing trader
- weather temperature specialist

Market-category playbooks live under `docs/market_categories/`. When a new
class of wallet appears, create a playbook before promoting factors.

## Stage 6: Agent Research

Goal: convert raw artifacts into a human-readable research conclusion.

Outputs:

- `research_report.md`
- `candidate_factors.json`
- `next_commands.json`
- `sop_status.json`

The agent is allowed to propose candidates and next experiments. It must not
claim strategy replication unless the required data sources and validation
artifacts exist.

## Stage 7: Promotion

Goal: turn a useful research idea into reusable code.

Promotion checklist:

- Add the factor implementation under `profiler/okprofiler/features/`.
- Register it in `FACTOR_SPECS`.
- Add it to `docs/factors.md`.
- Add or update the market playbook under `docs/market_categories/`.
- Re-run the target profile and confirm non-null factor coverage.
- Mark whether the factor is offline-only or live-ready.

## Stage 8: Evidence Expansion

Goal: strengthen the claim from "wallet behavior described" to "strategy can be
partially replicated."

Common expansion paths:

- CLOB data for OFI, spread, depth imbalance, and momentum.
- Weather observations for settlement outcome checks.
- Weather forecast history for `forecast_error_to_bucket` and forecast-delta
  factors.
- News timelines for information-edge accounts.

If `diagnostics.json` still has `missing_actions`, the SOP should be treated as
research-in-progress even when the main report exists.

## Research Loop

1. Run `python scripts/research_user.py <user> data/oktrader.sqlite`.
2. Read `research_report.md`, `diagnostics.json`, and `sop_status.json`.
3. Run commands listed in `next_commands.json`.
4. If a candidate factor requires a new adapter, implement the adapter first.
5. Promote proven candidates into the factor library.
6. Re-run the same profile and compare the new report.

The key rule is simple: every conclusion must map back to an artifact, and
every reusable idea must eventually become a registered factor or playbook.
