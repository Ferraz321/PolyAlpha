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
| `forward_price_move` | fills | Next observed market fill price move after this fill. | No | active |
| `entry_forward_edge` | fills | Direction-adjusted next-fill move after wallet entry. | No | active |
| `entry_before_move_secs` | fills | Seconds from entry to next favorable observed market move. | No | active |
| `lead_time_evidence` | fills | Directional edge normalized by time to the next observed market move. | No | active |
| `entry_price_advantage` | fills | Buy entry price versus same-market mean price. | No | active |
| `exit_quality_proxy` | fills | Sell price versus wallet's average buy price in the same market. | No | active |
| `sector_concentration` | markets | Share of wallet activity concentrated in the same sector. | No | active |
| `sector_trade_count` | markets | Number of wallet fills in the same sector. | No | active |
| `sector_pnl_proxy` | markets | Signed notional proxy aggregated by wallet and sector. | No | active |
| `resolution_lead_time_hours` | markets | Hours from fill to market resolution/end. | No | active |
| `news_recency_hours` | news | Hours between latest news item and wallet fill. | No | experimental |
| `news_reaction_window` | news | Whether fill occurred within six hours after latest news. | No | experimental |
| `repeat_hour_motif_score` | fills | Share of wallet activity recurring in the same UTC entry hour. | No | active |
| `repeat_entry_motif_count` | fills | Count of repeated account/market/side/hour motifs. | No | active |
| `repeat_market_add_rate` | fills | Same-market re-entry count normalized by wallet activity. | No | active |
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
| `actual_temp_distance_to_bucket` | weather observations | Actual daily high distance from the traded bucket. | No | active |
| `actual_temp_inside_bucket` | weather observations | Whether actual daily high landed inside the traded bucket. | No | active |
| `actual_temp_error_to_mid_f` | weather observations | Actual daily high minus bucket midpoint. | No | active |
| `forecast_temp_f` | weather forecast history | Historical forecast temperature aligned before wallet fill. | No | active |
| `forecast_error_to_bucket` | weather forecast history | Forecast temperature distance from traded bucket. | No | active |
| `forecast_inside_bucket` | weather forecast history | Whether forecast temperature was inside traded bucket. | No | active |
| `forecast_delta_1h` | weather forecast history | One-hour forecast temperature revision. | No | active |
| `forecast_delta_6h` | weather forecast history | Six-hour forecast temperature revision. | No | active |
| `forecast_volatility` | weather forecast history | Short-window forecast temperature volatility. | No | active |
| `weather_low_price_bucket_value` | fills | Weather temperature bucket fill priced below 20c. Used to test low-probability bucket value behavior. | No | active |
| `nwp_node_lag_secs` | fills | Seconds since the latest 00Z/06Z/12Z/18Z weather model run node. | No | active |
| `late_day_temperature_nowcast_edge` | fills | Whether fill occurred in the 18Z-22Z UTC window often relevant for same-day US temperature monitoring. | No | active |
| `official_station_source_available` | weather event metadata | Whether the market's official station/source was parsed from Gamma event rules. | No | active |
| `official_station_basis` | weather event metadata + official observations | Difference between official station high and generic/grid actual high. Non-null only when official observed high is available. | No | active-unvalidated |
| `temperature_bucket_ladder_mispricing` | weather event metadata / sibling prices | Absolute gap between entry price and same-bucket ladder reference price when live/open ladder prices are available. | No | active-unvalidated |

## Candidate Factors To Add

| Candidate | Required Data | Why It Matters |
| --- | --- | --- |
| `model_disagreement` | external weather | Compare multiple forecast models for mispricing. |
| `official_station_basis` | market rules + official weather station observations | Captures the gap between generic weather APIs and the exact station/source used for Polymarket settlement. |
| `official_station_target_bucket_edge` | intraday official station observations + sibling prices | Combined weather entry factor: official station high-to-date / target bucket distance / sibling ladder state at fill time. |
| `city_temperature_bias_edge` | official observations + forecast history | Measures persistent city/model forecast error that can explain repeat edge in specific cities. |
| `temperature_bucket_ladder_mispricing` | sibling market prices + bucket semantics | Compares adjacent temperature buckets on the same city-day to find incoherent probability mass across the ladder. |
| `market_breadth_rate` | fills | Separate broad stat-arb from narrow sniping. |
| `time_of_day_bucket` | fills | Detect scheduled or timezone-driven execution. |
| `bbo_exit_quality` | CLOB BBO | Measures whether unwind exits near favorable BBO, beyond the fill-only proxy. |
| `exit_fillability` | CLOB BBO + fills | Measures whether the position could realistically be sold at/near observed exit prices and size. |
| `strategy_capacity_usd` | CLOB depth + fills | Estimates maximum repeatable notional before spread/slippage consumes expected edge. |

## Promotion Rule

Only call a factor active when:

- the source data is present in `diagnostics.json`,
- it has non-null rows in `factor_table.parquet`,
- it appears in `factor_summary.md`,
- and the report clearly marks whether it is live-ready or offline-only.
