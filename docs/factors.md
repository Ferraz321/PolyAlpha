# OKTRADER Factor Catalog

This catalog is the human-maintained factor map. The executable registry lives
in `profiler/okprofiler/features/registry.py`; keep both aligned when promoting
a research idea into production.

## Active Factors

| Factor | Source | Meaning | Live Ready | Status |
| --- | --- | --- | --- | --- |
| `trade_notional` | fills | Single-trade ticket size, `price * shares`. | No | active |
| `ofi_filled` | CLOB | Signed order-flow imbalance proxy. | Yes, `ofi` | active |
| `spread_filled` | CLOB | Best ask minus best bid. | Yes, `spread` | active |
| `depth_imbalance_filled` | CLOB | `(bid_depth - ask_depth) / total_depth`. | Yes, `depth_imbalance` | active |
| `price_momentum` | CLOB | Short-horizon mid-price change by market. | Yes, `price_momentum` | active |
| `abs_price_momentum` | CLOB | Absolute short-horizon mid-price move. | No | active |
| `feature_lag_secs` | CLOB | Fill-to-feature as-of alignment lag. | No | active |
| `distance_to_bid` | CLOB | Fill price distance from best bid. | No | active |
| `distance_to_ask` | CLOB | Best ask distance from fill price. | No | active |
| `time_to_resolution_secs` | markets | Time from fill to market resolution/end. | No | active |
| `pre_news_lag_secs` | news | Time from most recent news item to fill. | No | experimental |

## Candidate Factors To Add

| Candidate | Required Data | Why It Matters |
| --- | --- | --- |
| `sector_concentration` | markets | Detect information edge limited to domains. |
| `market_breadth_rate` | fills | Separate broad stat-arb from narrow sniping. |
| `entry_before_move_secs` | CLOB/future price | Measures whether wallet enters before price moves. |
| `exit_quality` | fills/CLOB | Measures whether unwind exits near favorable BBO. |
| `time_of_day_bucket` | fills | Detect scheduled or timezone-driven execution. |
| `repeat_market_add_rate` | fills | Detect averaging-in versus one-shot betting. |

## Promotion Rule

Only call a factor active when:

- the source data is present in `diagnostics.json`,
- it has non-null rows in `factor_table.parquet`,
- it appears in `factor_summary.md`,
- and the report clearly marks whether it is live-ready or offline-only.
