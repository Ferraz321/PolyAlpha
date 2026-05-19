# Research Case: @beefslayer Weather-Temperature Specialist

Generated from the OKTRADER automated user research flow.

## Subject

- Polymarket profile: `@beefslayer`
- Resolved wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`
- Profile directory used for this run: `data/profiler_autotest_beefslayer`
- Public trade samples: `3020`
- Buy samples: `2085`
- Sell samples: `935`

## Data Coverage

| Source | Status | Rows |
| --- | --- | ---: |
| Public wallet fills | ready | 3020 |
| Gamma market metadata | ready | 200 |
| Open-Meteo actual observations | ready | 853 |
| Open-Meteo historical forecasts | ready | 41400 |
| CLOB microstructure | missing | 0 |
| News timeline | missing | 0 |

The run is strong enough for account specialization and weather-factor
research. It is not yet sufficient for CLOB-driven claims such as OFI, spread,
depth imbalance, or entry-before-move.

## Classification

- Account type: `weather_temperature`
- Label: weather temperature specialist
- Confidence: `86.79%`
- Best rule: `weather_market_ratio >= 0.867881`
- Explainability score: `0.9226`

Interpretation: this wallet is not casually trading weather. Its activity is
dominated by weather/temperature contracts across many markets and cities.

## Core Account Factors

| Factor | Value |
| --- | ---: |
| `weather_market_ratio` | 86.79% |
| `weather_market_breadth` | 1137 markets |
| `weather_city_count` | 18 cities |
| `weather_city_concentration` p50 | 10.79% |
| `temperature_bucket_width_f` p50 | 1.0°F |
| `temperature_mid_f` p50 | 56.5°F |
| `buy_ratio` | 69.04% |
| `same_market_reentry_count` p50 / p90 | 3 / 7 |
| `trade_notional` p50 / p90 | $17.26 / $158.06 |

The pattern looks like broad weather-market coverage with narrow temperature
buckets, repeated entries, and mostly buy-side directional exposure.

## Actual Weather Outcome Factors

| Factor | Coverage | p50 | p90 |
| --- | ---: | ---: | ---: |
| `actual_temp_distance_to_bucket` | 1324 rows | 2.10°F | 7.10°F |
| `actual_temp_inside_bucket` | 1324 rows | 0.0 | 1.0 |
| `actual_temp_error_to_mid_f` | 1125 rows | 0.40°F | 6.56°F |

These factors compare final observed temperatures to the traded bucket. They
help evaluate whether the wallet tends to enter buckets that later resolve
close to realized weather.

## Historical Forecast Factors

| Factor | Coverage | p50 | p90 |
| --- | ---: | ---: | ---: |
| `forecast_temp_f` | 2621 rows | 53.7°F | 77.0°F |
| `forecast_error_to_bucket` | 2523 rows | 1.70°F | 7.10°F |
| `forecast_inside_bucket` | 2523 rows | 0.0 | 1.0 |
| `forecast_delta_1h` | 2603 rows | 0.0°F | 3.90°F |
| `forecast_delta_6h` | 2513 rows | 0.40°F | 11.00°F |
| `forecast_volatility` | 2531 rows | 2.54°F | 7.99°F |

These are now active OKTRADER factors, not just candidate ideas. They let future
runs test whether the wallet enters when the current forecast is close to the
selected bucket or when forecasts are revising quickly.

## Current Hypothesis

`@beefslayer` appears to be a weather-temperature specialist that scans many
temperature markets rather than relying on a single city. The strongest current
evidence is specialization and breadth. The next question is whether entry
timing is driven by forecast proximity, forecast revision, or city-specific
model error.

Likely strategy family:

- weather forecast discrepancy
- narrow temperature bucket selection
- cross-city systematic coverage
- repeated same-market entry rather than one-shot betting

## Research Iteration 2026-05-19: New Factors

This pass discovered reusable candidate factors and recorded their definitions
in the central factor library:

- `weather_low_price_bucket_value`
- `nwp_node_lag_secs`
- `late_day_temperature_nowcast_edge`
- `official_station_basis`
- `city_temperature_bias_edge`
- `temperature_bucket_ladder_mispricing`

Validation update after implementation and profiler rerun:

- `weather_low_price_bucket_value`: implemented, but rejected by walk-forward
  behavior validation. It should not be treated as a confirmed standalone
  strategy factor.
- `late_day_temperature_nowcast_edge`: implemented, but rejected by
  walk-forward behavior validation. Time clustering exists, but the factor
  alone does not explain the wallet.
- `nwp_node_lag_secs`: implemented and kept as `researching`; it is useful as a
  timing diagnostic but does not confirm immediate model-release sniping.
- `official_station_basis`: partially implemented through Gamma event-context
  metadata. The first 25 weather events produced 275 ladder rows and parsed
  station IDs such as `KLGA`, `KHOU`, `KSEA`, `RKSI`, `KATL`, and `KORD`.
  The actual basis value is still blocked until official station observed highs
  are ingested.
- `temperature_bucket_ladder_mispricing`: partially implemented through Gamma
  ladder metadata. The first 25 weather events all produced valid ladder rows,
  but the sampled markets are closed, so final ladder prices cannot prove
  at-entry mispricing. Historical or live sibling prices are still required.

Latest validation note:

- Official station observations were fetched for 25 station/date rows. For the
  successfully fetched US stations, official-settlement PnL on 109
  bucket-bounded rows was +$225.12, 11.78% ROI, with 81.13% win rate. This
  confirms official station data is required for correct settlement/PnL, but
  `official_station_basis` alone was rejected as a standalone entry trigger.
- Historical sibling prices from CLOB `prices-history` were tested on 3 events
  and 47 fills. The sample was profitable (+$24.05, 5.8% ROI), but a simple
  ladder alignment split did not isolate the edge. The next hypothesis is a
  combined factor: official-station nowcast plus target-bucket/adjacent-bucket
  exclusion, not ladder shape alone.
- New candidate `official_station_target_bucket_edge` records that combined
  hypothesis. It is intentionally blocked until intraday official station
  observations before each fill are available; using final official high would
  leak the settlement answer into the entry signal.

## Research Iteration 2026-05-19: Factor Mining Follow-Up

The next factor-mining pass promoted three blocked ideas into executable,
offline-only research columns:

- `model_disagreement`: aggregates multiple forecast sources at the same
  city/timestamp and records the temperature range across models.
- `city_temperature_bias_edge`: measures realized-minus-forecast bias and the
  city-level mean absolute bias. This is an ex-post research label, not a live
  entry signal.
- `official_station_target_bucket_edge`: uses only official station
  `official_high_to_date_f` observed before the fill, plus entry price and
  ladder mispricing. It intentionally excludes final official high from the
  entry signal to avoid settlement leakage.

Synthetic profiler smoke confirmed the new columns are produced correctly when
multi-model forecasts and intraday station high-to-date observations are
present. Real promotion still requires larger historical multi-model forecast
and official intraday station datasets.

Updated behavioral read:

- The account is a temperature-bucket specialist, not a hurricane-path or
  extreme-weather-days specialist.
- Its public sample is dominated by taker fills, so the observed behavior is
  active execution rather than passive market making.
- The timing profile does not look like a clean "new GRIB file arrives, trade
  within seconds" bot. It is more consistent with monitoring late-day city
  temperature paths and finding bucket-ladder mispricings.
- The highest-priority missing source is official settlement-grade station data,
  because 1°F bucket markets are too sensitive for generic actual-weather
  proxies.

## Remaining Evidence Gaps

- CLOB snapshots are missing, so OFI/spread/depth/momentum claims are not yet
  supported.
- News timeline is missing, so pre-news information-edge claims are not tested.
- Settlement-grade realized PnL by city and weather category still needs a
  stronger closed-loop/settlement model.
- Multi-model weather disagreement is implemented as an active-unvalidated
  research factor; it still needs real multi-model forecast coverage for
  promotion.

## Next Research Tasks

1. Build `official_station_basis`: map each city market to the official station
   or source used by settlement, then compare it with Open-Meteo/grid actuals.
2. Build `temperature_bucket_ladder_mispricing`: reconstruct all sibling bucket
   prices for the same city-day at each fill timestamp.
3. Build `late_day_temperature_nowcast_edge`: align fills with hourly official
   station observations and local city time.
4. Keep `nwp_node_lag_secs` as a negative/diagnostic factor: use it to reject or
   confirm model-release-sniping rather than assuming it.
5. Add negative controls from non-wallet weather fills for precision/recall.
