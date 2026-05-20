# OKTRADER Factor Catalog

This document is the human-facing factor map. The code source of truth lives in
`profiler/okprofiler/features/catalog.py`; the executable registry in
`profiler/okprofiler/features/registry.py` is generated from that catalog.
`profiler/okprofiler/features/library.py` contains one `FactorImplementation`
per factor and is the execution library used by `add_derived_factors`.

To inspect the live catalog:

```bash
python profiler/profile_wallets.py list-factors
python profiler/profile_wallets.py list-factors --category sector
```

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
| `prior_same_market_trade_count` | fills | Causal count of prior fills by the wallet in the same market before current fill. | No | active |
| `prior_market_reentry_rate` | fills | Prior same-market count normalized by prior account activity. | No | active |
| `prior_repeat_entry_motif_count` | fills | Causal count of prior account/market/side/hour motifs. | No | active |
| `prior_repeat_hour_motif_score` | fills | Prior share of wallet activity recurring in the same UTC entry hour. | No | active |
| `prior_buy_ratio` | fills | Buy-side ratio using only prior fills. | No | active |
| `hour_motif_timing_edge` | fills | UTC entry hour weighted by prior repeat-hour behavior. | No | confirmed-effective on beefslayer profile |
| `temperature_motif_edge` | fills + weather semantics | Temperature bucket midpoint weighted by prior repeat-hour behavior. | No | confirmed-effective on beefslayer profile |
| `prior_reentry_hour_motif_edge` | fills | Prior same-market activity weighted by prior repeat-hour behavior. | No | confirmed-effective on beefslayer profile |
| `prior_reentry_buy_bias_edge` | fills | Prior same-market activity weighted by prior buy-side bias. | No | confirmed-effective on beefslayer profile |
| `forward_price_move` | fills | Next observed market fill price move after this fill. | No | active |
| `entry_forward_edge` | fills | Direction-adjusted next-fill move after wallet entry. | No | active |
| `entry_before_move_secs` | fills | Seconds from entry to next favorable observed market move. | No | active |
| `lead_time_evidence` | fills | Directional edge normalized by time to the next observed market move. | No | active |
| `entry_price_advantage` | fills | Buy entry price versus same-market mean price. | No | active |
| `exit_quality_proxy` | fills | Sell price versus wallet's average buy price in the same market. | No | active |
| `sector_concentration` | markets | Share of wallet activity concentrated in the same sector. | No | active |
| `sector_trade_count` | markets | Number of wallet fills in the same sector. | No | active |
| `sector_pnl_proxy` | markets | Signed notional proxy aggregated by wallet and sector. | No | active |
| `sector_entry_edge` | markets + fills | Mean direction-adjusted next-fill edge for the same wallet and sector. | No | active-unvalidated |
| `sector_repeat_edge_score` | markets + fills | Sector concentration multiplied by positive entry-forward edge. | No | active-unvalidated |
| `sector_motif_consistency_edge` | markets + fills | Sector concentration and repeated entry-hour behavior weighted by positive entry-forward edge. | No | active-unvalidated |
| `cross_sector_breadth` | markets | One minus sector concentration; identifies broad scanners instead of narrow specialists. | No | active-unvalidated |
| `resolution_lead_time_hours` | markets | Hours from fill to market resolution/end. | No | active |
| `settlement_window_edge` | markets + fills | Positive entry-forward edge gated to final-24h settlement-window entries. | No | active-unvalidated |
| `settlement_urgency_edge` | markets + fills | Final-24h positive entry-forward edge divided by hours remaining to resolution. | No | active-unvalidated |
| `news_recency_hours` | news | Hours between latest news item and wallet fill. | No | experimental |
| `news_reaction_window` | news | Whether fill occurred within six hours after latest news. | No | experimental |
| `news_lead_entry_edge` | news + fills | Positive entry-forward edge gated to post-news reaction windows. | No | active-unvalidated |
| `news_recency_decay_edge` | news + fills | Positive entry-forward edge decayed by hours since the latest news item. | No | active-unvalidated |
| `microstructure_entry_edge` | CLOB + fills | Entry-forward edge weighted by order-flow, depth, momentum, and spread context. | No | active-unvalidated |
| `microstructure_pressure_score` | CLOB | Positive CLOB pressure from order flow, depth, momentum, and spread. | No | active-unvalidated |
| `microstructure_pressure_edge` | CLOB + fills | Positive entry-forward edge multiplied by positive CLOB pressure. | No | active-unvalidated |
| `repeat_hour_motif_score` | fills | Share of wallet activity recurring in the same UTC entry hour. | No | active |
| `repeat_entry_motif_count` | fills | Count of repeated account/market/side/hour motifs. | No | active |
| `repeat_market_add_rate` | fills | Same-market re-entry count normalized by wallet activity. | No | active |
| `event_motif_recurrence` | fills | Repeated hour/market/side motif strength weighted by positive entry-forward edge. | No | active-unvalidated |
| `is_weather_market` | fills | Whether event slug matches weather temperature market grammar. | No | active |
| `weather_market_ratio` | fills | Share of wallet fills in weather markets. | No | active |
| `weather_city_concentration` | fills | Share of wallet fills concentrated in the same weather city. | No | active |
| `weather_market_breadth` | fills | Number of distinct weather markets traded by the wallet. | No | active |
| `weather_city_count` | fills | Number of distinct weather cities traded by the wallet. | No | active |
| `temperature_mid_f` | fills | Parsed midpoint of temperature bucket in Fahrenheit. | No | active |
| `temperature_bucket_width_f` | fills | Parsed temperature bucket width. | No | active |
| `is_low_temp_bucket` | fills | Whether bucket midpoint is at or below 40°F. | No | active |
| `is_high_temp_bucket` | fills | Whether bucket midpoint is at or above 75°F. | No | confirmed-effective on beefslayer profile |
| `is_extreme_temperature_bucket` | fills | Whether bucket midpoint is at or below 32°F or at or above 90°F. | No | active |
| `actual_temp_distance_to_bucket` | weather observations | Actual daily high distance from the traded bucket. | No | diagnostic, ex-post |
| `actual_temp_inside_bucket` | weather observations | Whether actual daily high landed inside the traded bucket. | No | diagnostic, ex-post |
| `actual_temp_error_to_mid_f` | weather observations | Actual daily high minus bucket midpoint. | No | diagnostic, ex-post |
| `forecast_temp_f` | weather forecast history | Historical forecast temperature aligned before wallet fill. | No | active |
| `forecast_error_to_bucket` | weather forecast history | Forecast temperature distance from traded bucket. | No | confirmed-effective on beefslayer profile |
| `forecast_inside_bucket` | weather forecast history | Whether forecast temperature was inside traded bucket. | No | active |
| `forecast_delta_1h` | weather forecast history | One-hour forecast temperature revision. | No | active |
| `forecast_delta_6h` | weather forecast history | Six-hour forecast temperature revision. | No | active |
| `forecast_volatility` | weather forecast history | Short-window forecast temperature volatility. | No | active |
| `forecast_model_count` | weather forecast history | Number of distinct forecast sources/models available at the aligned forecast timestamp. | No | active |
| `model_disagreement` | weather forecast history | Temperature range across aligned forecast sources/models. | No | active-unvalidated |
| `forecast_bias_error_f` | weather forecast + observations | Ex-post realized temperature minus aligned forecast temperature. Used for research validation, not live entry by itself. | No | diagnostic, ex-post |
| `city_temperature_bias_edge` | weather forecast + observations | Absolute city-level mean forecast bias, used to test repeat city/model error. | No | diagnostic, ex-post |
| `bucket_distance_from_normal` | weather forecast history | Distance between traded bucket midpoint and city forecast normal/median in the sample. | No | diagnostic until made as-of |
| `weather_low_price_bucket_value` | fills | Weather temperature bucket fill priced below 20c. Used to test low-probability bucket value behavior. | No | active |
| `nwp_node_lag_secs` | fills | Seconds since the latest 00Z/06Z/12Z/18Z weather model run node. | No | active |
| `late_day_temperature_nowcast_edge` | fills | Whether fill occurred in the 18Z-22Z UTC window often relevant for same-day US temperature monitoring. | No | active |
| `official_station_source_available` | weather event metadata | Whether the market's official station/source was parsed from Gamma event rules. | No | active |
| `official_station_basis` | weather event metadata + official observations | Difference between official station high and generic/grid actual high. Non-null only when official observed high is available. | No | diagnostic, ex-post |
| `official_station_bucket_distance` | intraday official observations | Distance from official station high-to-date at fill time to the traded bucket. | No | active-unvalidated |
| `official_station_inside_bucket_now` | intraday official observations | Whether official station high-to-date is already inside the traded bucket at fill time. | No | active-unvalidated |
| `official_station_target_bucket_edge` | intraday official observations + sibling prices | Non-leaking proxy combining station high-to-date proximity, entry price, and ladder state. | No | active-unvalidated |
| `temperature_bucket_ladder_mispricing` | weather event metadata / sibling prices | Absolute gap between entry price and same-bucket ladder reference price when live/open ladder prices are available. | No | active-unvalidated |

## Candidate Factors To Add

| Candidate | Required Data | Why It Matters |
| --- | --- | --- |
| `official_station_basis` | market rules + official weather station observations | Captures the gap between generic weather APIs and the exact station/source used for Polymarket settlement. |
| `temperature_bucket_ladder_mispricing` | sibling market prices + bucket semantics | Compares adjacent temperature buckets on the same city-day to find incoherent probability mass across the ladder. |
| `market_breadth_rate` | fills | Separate broad stat-arb from narrow sniping. |
| `time_of_day_bucket` | fills | Detect scheduled or timezone-driven execution. |
| `bbo_exit_quality` | CLOB BBO | Measures whether unwind exits near favorable BBO, beyond the fill-only proxy. |
| `exit_fillability` | CLOB BBO + fills | Measures whether the position could realistically be sold at/near observed exit prices and size. |
| `strategy_capacity_usd` | CLOB depth + fills | Estimates maximum repeatable notional before spread/slippage consumes expected edge. |
| `sector_entry_edge` | fills + market sectors | Tests whether a wallet repeatedly enters one sector before favorable price movement. |
| `news_lead_entry_edge` | fills + news timeline | Tests whether a wallet consistently enters soon after external information before market repricing. |
| `settlement_window_edge` | fills + market resolution time | Tests whether late entries before resolution have repeatable positive edge. |
| `microstructure_entry_edge` | fills + CLOB state | Tests whether CLOB pressure explains profitable timing beyond wallet identity. |
| `microstructure_pressure_edge` | fills + CLOB state | Tests only positive CLOB pressure regimes instead of subtracting spread inside the edge score. |
| `news_recency_decay_edge` | fills + news timeline | Tests whether information edge decays smoothly with elapsed news time. |
| `settlement_urgency_edge` | fills + market resolution time | Tests whether late entries become stronger as resolution approaches. |
| `sector_motif_consistency_edge` | fills + market sectors | Tests repeated sector/time motifs after requiring favorable follow-through. |

## Promotion Rule

Only call a factor active when:

- the source data is present in `diagnostics.json`,
- it has non-null rows in `factor_table.parquet`,
- it appears in `factor_summary.md`,
- and the report clearly marks whether it is live-ready or offline-only.
