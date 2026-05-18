from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class FactorSpec:
    column: str
    label: str
    direction: str
    quantile: float
    live_feature: str | None = None
    requires: tuple[str, ...] = ()


FACTOR_SPECS = [
    FactorSpec("ofi_filled", "order-flow imbalance", "high", 0.90, "ofi", ("clob_features",)),
    FactorSpec("spread_filled", "tight spread", "low", 0.50, "spread", ("clob_features",)),
    FactorSpec("depth_imbalance_filled", "depth imbalance", "high", 0.50, "depth_imbalance", ("clob_features",)),
    FactorSpec("price_momentum", "short-horizon price momentum", "high", 0.50, "price_momentum", ("clob_features",)),
    FactorSpec("abs_price_momentum", "absolute price shock", "high", 0.90, None, ("clob_features",)),
    FactorSpec("feature_lag_secs", "fresh CLOB alignment", "low", 0.50, None, ("clob_features",)),
    FactorSpec("distance_to_bid", "entry near bid", "low", 0.50, None, ("clob_features",)),
    FactorSpec("distance_to_ask", "entry near ask", "low", 0.50, None, ("clob_features",)),
    FactorSpec("trade_notional", "ticket size", "high", 0.75, None, ("fills",)),
    FactorSpec("time_to_resolution_secs", "time to resolution", "high", 0.50, None, ("markets",)),
    FactorSpec("pre_news_lag_secs", "pre-news timing", "low", 0.25, None, ("news",)),
    FactorSpec("is_weather_market", "weather market specialization", "high", 0.50, None, ("fills",)),
    FactorSpec("weather_market_ratio", "weather trader specialization", "high", 0.50, None, ("fills",)),
    FactorSpec("weather_city_concentration", "weather city concentration", "high", 0.75, None, ("fills",)),
    FactorSpec("weather_market_breadth", "weather market breadth", "high", 0.50, None, ("fills",)),
    FactorSpec("weather_city_count", "weather city breadth", "high", 0.50, None, ("fills",)),
    FactorSpec("temperature_mid_f", "temperature bucket midpoint", "high", 0.50, None, ("fills",)),
    FactorSpec("temperature_bucket_width_f", "temperature bucket width", "low", 0.50, None, ("fills",)),
    FactorSpec("is_low_temp_bucket", "low-temperature bucket", "high", 0.50, None, ("fills",)),
    FactorSpec("is_high_temp_bucket", "high-temperature bucket", "high", 0.50, None, ("fills",)),
    FactorSpec("is_extreme_temperature_bucket", "extreme-temperature bucket", "high", 0.50, None, ("fills",)),
    FactorSpec("actual_temp_distance_to_bucket", "actual temp distance to bucket", "low", 0.50, None, ("weather_observations",)),
    FactorSpec("actual_temp_inside_bucket", "actual temp inside bucket", "high", 0.50, None, ("weather_observations",)),
    FactorSpec("actual_temp_error_to_mid_f", "actual temp error to midpoint", "low", 0.50, None, ("weather_observations",)),
    FactorSpec("forecast_temp_f", "historical forecast temperature", "high", 0.50, None, ("weather_forecasts",)),
    FactorSpec("forecast_error_to_bucket", "forecast distance to bucket", "low", 0.50, None, ("weather_forecasts",)),
    FactorSpec("forecast_inside_bucket", "forecast inside bucket", "high", 0.50, None, ("weather_forecasts",)),
    FactorSpec("forecast_delta_1h", "forecast 1h revision", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("forecast_delta_6h", "forecast 6h revision", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("forecast_volatility", "forecast short-window volatility", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("entry_hour_utc", "entry hour UTC", "low", 0.50, None, ("fills",)),
    FactorSpec("is_last_24h", "last 24h entry", "high", 0.50, None, ("markets",)),
    FactorSpec("is_last_6h", "last 6h entry", "high", 0.50, None, ("markets",)),
    FactorSpec("same_market_reentry_count", "same-market reentry count", "high", 0.75, None, ("fills",)),
    FactorSpec("buy_ratio", "wallet buy-side ratio", "high", 0.50, None, ("fills",)),
]


def available_specs(df: pl.DataFrame) -> list[FactorSpec]:
    return [spec for spec in FACTOR_SPECS if spec.column in df.columns]
