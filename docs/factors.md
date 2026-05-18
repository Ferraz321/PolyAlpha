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
| `entry_hour_utc` | fills | UTC hour of the wallet entry. | No | active |
| `is_last_24h` | markets | Whether fill is inside the final 24 hours before resolution. | No | active |
| `is_last_6h` | markets | Whether fill is inside the final 6 hours before resolution. | No | active |
| `same_market_reentry_count` | fills | Number of fills by the wallet in the same market. | No | active |
| `buy_ratio` | fills | Wallet-level buy-side fill ratio. | No | active |
| `is_weather_market` | fills | Whether event slug matches weather temperature market grammar. | No | active |
| `weather_market_ratio` | fills | Share of wallet fills in weather markets. | No | active |
| `weather_city_concentration` | fills | Share of wallet fills concentrated in the same weather city. | No | active |
| `weather_market_breadth` | fills | Number of distinct weather markets traded by the wallet. | No | active |
| `weather_city_count` | fills | Number of distinct weather cities traded by the wallet. | No | active |
| `temperature_mid_f` | fills | Parsed midpoint of temperature bucket in Fahrenheit. | No | active |
| `temperature_bucket_width_f` | fills | Parsed temperature bucket width. | No | active |
| `is_low_temp_bucket` | fills | Whether bucket midpoint is at or below 40°F. | No | active |
| `is_high_temp_bucket` | fills | Whether bucket midpoint is at or above 75°F. | No | active |
| `is_extreme_temperature_bucket` | fills | Whether bucket midpoint is at or below 32°F or at or above 90°F. | No | active |

## Candidate Factors To Add

| Candidate | Required Data | Why It Matters |
| --- | --- | --- |
| `sector_concentration` | markets | Detect information edge limited to domains. |
| `forecast_error_to_bucket` | external weather | Compare forecast temperature to traded bucket. |
| `forecast_delta_1h` | external weather | Detect forecast revisions shortly before entry. |
| `forecast_delta_6h` | external weather | Detect larger weather model revision windows. |
| `forecast_inside_bucket` | external weather | Check whether forecast already lands inside the traded bucket. |
| `model_disagreement` | external weather | Compare multiple forecast models for mispricing. |
| `actual_temp_distance_to_bucket` | external weather | Final realized temperature distance from traded bucket. |
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
