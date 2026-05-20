# Factor Discovery Report

- source_factor_table: data/profiler_real_beefslayer/factor_table.parquet
- category: weather_temperature
- rows: 3020
- registered_candidates: 16
- synthetic_candidates: 80
- summary: confirmed_effective=7, confirmed_promising=25, confirmed_rejected=64

## Confirmed Effective

| Factor | Category | Approved | OOS | Replication | Stability | Formula |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `discovered__is_high_temp_bucket__x__weather_low_price_bucket_value` | discovered | 4/4 | 0.0304 | 0.4167 | 1.0000 | is_high_temp_bucket * weather_low_price_bucket_value |
| `temperature_motif_edge` | weather_timing | 3/4 | 0.0285 | 0.6667 | 0.7402 | temperature_motif_edge |
| `discovered__temperature_motif_edge__x__is_weather_market` | discovered | 3/4 | 0.0285 | 0.6667 | 0.7402 | temperature_motif_edge * is_weather_market |
| `discovered__temperature_motif_edge__x__weather_city_concentration` | discovered | 3/4 | 0.0275 | 0.5000 | 0.8007 | temperature_motif_edge * weather_city_concentration |
| `discovered__weather_city_concentration__x__forecast_error_to_bucket` | discovered | 3/4 | 0.0270 | 0.5000 | 0.9806 | weather_city_concentration * forecast_error_to_bucket |
| `is_high_temp_bucket` | weather_semantic | 3/4 | 0.0256 | 0.5833 | 1.0000 | is_high_temp_bucket |
| `discovered__is_weather_market__x__is_high_temp_bucket` | discovered | 3/4 | 0.0256 | 0.5833 | 1.0000 | is_weather_market * is_high_temp_bucket |

## Confirmed Promising

| Factor | Category | Approved | OOS | Replication | Stability | Formula |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `discovered__temperature_motif_edge__x__temperature_mid_f` | discovered | 2/4 | 0.0229 | 0.6667 | 0.4379 | temperature_motif_edge * temperature_mid_f |
| `discovered__late_day_temperature_nowcast_edge__x__is_high_temp_bucket` | discovered | 1/4 | 0.0198 | 0.5000 | 1.0000 | late_day_temperature_nowcast_edge * is_high_temp_bucket |
| `discovered__temperature_motif_edge__x__forecast_temp_f` | discovered | 1/4 | 0.0176 | 0.6667 | 0.4397 | temperature_motif_edge * forecast_temp_f |
| `is_extreme_temperature_bucket` | weather_semantic | 1/4 | 0.0139 | 0.2500 | 1.0000 | is_extreme_temperature_bucket |
| `discovered__is_weather_market__x__is_extreme_temperature_bucket` | discovered | 1/4 | 0.0139 | 0.2500 | 1.0000 | is_weather_market * is_extreme_temperature_bucket |
| `discovered__nwp_node_lag_secs__x__late_day_temperature_nowcast_edge` | discovered | 1/4 | 0.0134 | 0.5833 | 0.6960 | nwp_node_lag_secs * late_day_temperature_nowcast_edge |
| `discovered__temperature_motif_edge__x__late_day_temperature_nowcast_edge` | discovered | 1/4 | 0.0120 | 0.5000 | 0.5571 | temperature_motif_edge * late_day_temperature_nowcast_edge |
| `discovered__is_weather_market__x__temperature_mid_f` | discovered | 1/4 | 0.0106 | 0.5000 | 0.7064 | is_weather_market * temperature_mid_f |
| `weather_city_concentration` | weather_semantic | 0/4 | 0.0359 | 0.0000 | 0.6231 | weather_city_concentration |
| `discovered__weather_city_concentration__x__is_weather_market` | discovered | 0/4 | 0.0359 | 0.0000 | 0.6231 | weather_city_concentration * is_weather_market |
| `discovered__weather_city_concentration__x__late_day_temperature_nowcast_edge` | discovered | 0/4 | 0.0257 | 0.1667 | 0.8763 | weather_city_concentration * late_day_temperature_nowcast_edge |
| `discovered__weather_city_concentration__x__forecast_delta_6h` | discovered | 0/4 | 0.0235 | 0.5556 | 0.1165 | weather_city_concentration * forecast_delta_6h |

