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

## Candidate External Weather Factors

- `model_disagreement`: spread between forecast providers/models.
- `bucket_distance_from_normal`: distance from city seasonal normal.

## Interpretation

A high `weather_market_ratio` only proves specialization. A reusable weather
strategy requires evidence that entries cluster around forecast errors,
forecast revisions, city-specific edge, or final-window resolution timing.
