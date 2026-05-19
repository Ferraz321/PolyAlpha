# Weather Temperature Market Playbook

This playbook is the required reverse-engineering checklist for wallets whose
`weather_market_ratio` is at least `0.50`.

## Active Factor Groups

### Account Specialization

- `weather_market_ratio`: share of wallet fills in weather markets.
- `weather_market_breadth`: distinct weather markets traded.
- `weather_city_count`: distinct weather cities traded.
- `weather_city_concentration`: concentration in the same city.

### Contract Semantics

- `temperature_mid_f`: midpoint of the traded temperature bucket.
- `temperature_bucket_width_f`: bucket width in Fahrenheit.
- `is_low_temp_bucket`: low-temperature bucket preference.
- `is_high_temp_bucket`: high-temperature bucket preference.
- `is_extreme_temperature_bucket`: extreme cold/hot bucket preference.

### Timing

- `time_to_resolution_secs`: seconds from fill to market resolution.
- `is_last_24h`: final-day entry flag.
- `is_last_6h`: final-six-hour entry flag.
- `entry_hour_utc`: entry hour for scheduled behavior.

### Trading Behavior

- `trade_notional`: single-fill notional size.
- `same_market_reentry_count`: repeat entries in the same market.
- `buy_ratio`: buy-side fill ratio.

### Actual Weather Outcome

- `actual_temp_distance_to_bucket`: realized daily high distance from bucket.
- `actual_temp_inside_bucket`: whether realized daily high landed in bucket.
- `actual_temp_error_to_mid_f`: realized daily high minus bucket midpoint.

### Historical Forecast Context

- `forecast_temp_f`: forecast temperature at entry time.
- `forecast_error_to_bucket`: forecast distance from the traded bucket.
- `forecast_inside_bucket`: whether forecast lands inside the bucket.
- `forecast_delta_1h`: one-hour forecast revision.
- `forecast_delta_6h`: six-hour forecast revision.
- `forecast_volatility`: recent forecast instability.
- `nwp_node_lag_secs`: seconds since the latest 00Z/06Z/12Z/18Z model-run node.

### Weather Execution Hypotheses

- `weather_low_price_bucket_value`: low-probability temperature-bucket value entry.
- `late_day_temperature_nowcast_edge`: same-day temperature-monitoring time window.
- `official_station_source_available`: parsed official station/source exists for the market.
- `official_station_basis`: official station high minus generic/grid high.
- `temperature_bucket_ladder_mispricing`: entry price gap versus same-bucket ladder reference price when sibling prices are available.

## Candidate External Weather Factors

- `model_disagreement`: spread between forecast providers/models.
- `bucket_distance_from_normal`: distance from city seasonal normal.
- `official_station_basis`: difference between a generic/grid weather source and the official settlement station/source for the market.
- `official_station_target_bucket_edge`: official station high-to-date and remaining path versus the target bucket, combined with sibling ladder prices at fill time.
- `city_temperature_bias_edge`: repeatable city-specific forecast error versus official observed high.
- `temperature_bucket_ladder_mispricing`: mispricing across adjacent buckets for the same city-day ladder.

## Event Context Data

Weather event context is fetched from Gamma event metadata with
`fetch-weather-event-contexts`. It extracts:

- `resolution_source`, e.g. a Wunderground station URL.
- `official_station_id`, e.g. `KLGA`, `KSEA`, `KATL`.
- sibling ladder rows with `ladder_yes_price`, `ladder_price_sum`, and
  `ladder_bucket_count`.

This data proves where settlement is supposed to come from, but it is not enough
to validate alpha by itself. `official_station_basis` still needs official
observed highs, and `temperature_bucket_ladder_mispricing` needs live/open or
historical sibling prices at the wallet's fill time.

## Interpretation

A high `weather_market_ratio` only proves specialization. A reusable weather
strategy requires evidence that entries cluster around forecast errors,
forecast revisions, city-specific edge, or final-window resolution timing.
