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
    FactorSpec("forecast_model_count", "forecast model/source count", "high", 0.50, None, ("weather_forecasts",)),
    FactorSpec("model_disagreement", "forecast model disagreement", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("forecast_bias_error_f", "forecast realized bias error", "high", 0.50, None, ("weather_forecasts",)),
    FactorSpec("city_temperature_bias_edge", "city temperature bias edge", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("bucket_distance_from_normal", "bucket distance from city normal", "high", 0.75, None, ("weather_forecasts",)),
    FactorSpec("entry_hour_utc", "entry hour UTC", "low", 0.50, None, ("fills",)),
    FactorSpec("nwp_node_lag_secs", "NWP model-node lag", "low", 0.25, None, ("fills",)),
    FactorSpec("late_day_temperature_nowcast_edge", "late-day temperature nowcast window", "high", 0.50, None, ("fills",)),
    FactorSpec("weather_low_price_bucket_value", "low-price weather bucket value", "high", 0.50, None, ("fills",)),
    FactorSpec("official_station_source_available", "official station source available", "high", 0.50, None, ("weather_events",)),
    FactorSpec("official_station_basis", "official station basis", "low", 0.50, None, ("weather_events", "weather_observations")),
    FactorSpec("official_station_bucket_distance", "official station bucket distance", "low", 0.50, None, ("weather_events", "official_weather")),
    FactorSpec("official_station_inside_bucket_now", "official station inside bucket now", "high", 0.50, None, ("weather_events", "official_weather")),
    FactorSpec("official_station_target_bucket_edge", "official station target bucket edge", "high", 0.75, None, ("weather_events", "official_weather")),
    FactorSpec("temperature_bucket_ladder_mispricing", "temperature bucket ladder mispricing", "high", 0.75, None, ("weather_events",)),
    FactorSpec("is_last_24h", "last 24h entry", "high", 0.50, None, ("markets",)),
    FactorSpec("is_last_6h", "last 6h entry", "high", 0.50, None, ("markets",)),
    FactorSpec("same_market_reentry_count", "same-market reentry count", "high", 0.75, None, ("fills",)),
    FactorSpec("buy_ratio", "wallet buy-side ratio", "high", 0.50, None, ("fills",)),
    FactorSpec("forward_price_move", "next market price move", "high", 0.50, None, ("fills",)),
    FactorSpec("entry_forward_edge", "directional entry edge", "high", 0.75, None, ("fills",)),
    FactorSpec("entry_before_move_secs", "entry before favorable move", "low", 0.50, None, ("fills",)),
    FactorSpec("lead_time_evidence", "entry lead-time evidence", "high", 0.75, None, ("fills",)),
    FactorSpec("entry_price_advantage", "entry price advantage", "high", 0.75, None, ("fills",)),
    FactorSpec("exit_quality_proxy", "exit quality proxy", "high", 0.75, None, ("fills",)),
    FactorSpec("sector_concentration", "sector concentration", "high", 0.75, None, ("markets",)),
    FactorSpec("sector_trade_count", "sector trade count", "high", 0.75, None, ("markets",)),
    FactorSpec("sector_pnl_proxy", "sector PnL proxy", "high", 0.75, None, ("markets",)),
    FactorSpec("sector_entry_edge", "sector entry edge", "high", 0.75, None, ("markets", "fills")),
    FactorSpec("sector_repeat_edge_score", "sector repeat edge score", "high", 0.75, None, ("markets", "fills")),
    FactorSpec("cross_sector_breadth", "cross-sector breadth", "high", 0.50, None, ("markets",)),
    FactorSpec("resolution_lead_time_hours", "resolution lead time hours", "high", 0.50, None, ("markets",)),
    FactorSpec("settlement_window_edge", "settlement window edge", "high", 0.75, None, ("markets", "fills")),
    FactorSpec("news_recency_hours", "news recency hours", "low", 0.25, None, ("news",)),
    FactorSpec("news_reaction_window", "news reaction window", "high", 0.50, None, ("news",)),
    FactorSpec("news_lead_entry_edge", "news lead-entry edge", "high", 0.75, None, ("news", "fills")),
    FactorSpec("microstructure_entry_edge", "microstructure entry edge", "high", 0.75, None, ("clob_features", "fills")),
    FactorSpec("repeat_hour_motif_score", "repeat hour motif score", "high", 0.75, None, ("fills",)),
    FactorSpec("repeat_entry_motif_count", "repeat entry motif count", "high", 0.75, None, ("fills",)),
    FactorSpec("repeat_market_add_rate", "repeat market add rate", "high", 0.75, None, ("fills",)),
    FactorSpec("event_motif_recurrence", "event motif recurrence", "high", 0.75, None, ("fills",)),
]


def available_specs(df: pl.DataFrame) -> list[FactorSpec]:
    return [spec for spec in FACTOR_SPECS if spec.column in df.columns]
