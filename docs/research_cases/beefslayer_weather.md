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

## Remaining Evidence Gaps

- CLOB snapshots are missing, so OFI/spread/depth/momentum claims are not yet
  supported.
- News timeline is missing, so pre-news information-edge claims are not tested.
- Settlement-grade realized PnL by city and weather category still needs a
  stronger closed-loop/settlement model.
- Multi-model weather disagreement is still a candidate factor.

## Next Research Tasks

1. Record CLOB for `clob_assets.txt` to test entry-before-move and liquidity
   timing.
2. Add `model_disagreement` using another weather model or provider.
3. Add city-specific realized PnL and win-rate factors.
4. Split the sample by time to verify that forecast thresholds are stable.
5. Add negative controls from non-wallet weather fills for real precision and
   recall.
