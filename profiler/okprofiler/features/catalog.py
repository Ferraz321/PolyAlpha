from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class FactorDefinition:
    column: str
    label: str
    direction: str
    quantile: float
    category: str
    calculation: str
    implemented_by: str
    live_feature: str | None = None
    requires: tuple[str, ...] = ()
    playbooks: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def fd(
    column: str,
    label: str,
    direction: str,
    quantile: float,
    category: str,
    calculation: str,
    implemented_by: str,
    live_feature: str | None = None,
    requires: tuple[str, ...] = (),
    playbooks: tuple[str, ...] = (),
) -> FactorDefinition:
    return FactorDefinition(
        column=column,
        label=label,
        direction=direction,
        quantile=quantile,
        category=category,
        calculation=calculation,
        implemented_by=implemented_by,
        live_feature=live_feature,
        requires=requires,
        playbooks=playbooks,
    )


FACTOR_DEFINITIONS = [
    fd("ofi_filled", "order-flow imbalance", "high", 0.90, "microstructure", "as-of CLOB ofi at fill time; null filled to 0", "pipeline.build_factor_table", "ofi", ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("spread_filled", "tight spread", "low", 0.50, "microstructure", "as-of best_ask - best_bid at fill time; null filled to 0", "pipeline.build_factor_table", "spread", ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("depth_imbalance_filled", "depth imbalance", "high", 0.50, "microstructure", "as-of (bid_depth - ask_depth) / (bid_depth + ask_depth); null filled to 0", "pipeline.build_factor_table", "depth_imbalance", ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("price_momentum", "short-horizon price momentum", "high", 0.50, "microstructure", "diff(mid_price) over market_id after CLOB as-of join", "pipeline.build_factor_table", "price_momentum", ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("abs_price_momentum", "absolute price shock", "high", 0.90, "microstructure", "abs(price_momentum)", "features.basic.add_basic_factors", None, ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("feature_lag_secs", "fresh CLOB alignment", "low", 0.50, "microstructure", "fill timestamp minus matched CLOB received_at in seconds; null filled to 999999", "pipeline.build_factor_table + features.basic", None, ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("distance_to_bid", "entry near bid", "low", 0.50, "microstructure", "fill price - as-of best_bid", "pipeline.build_factor_table", None, ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("distance_to_ask", "entry near ask", "low", 0.50, "microstructure", "as-of best_ask - fill price", "pipeline.build_factor_table", None, ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("microstructure_entry_edge", "microstructure entry edge", "high", 0.75, "microstructure", "max(entry_forward_edge, 0) * (ofi_filled + depth_imbalance_filled + price_momentum - spread_filled)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("clob_features", "fills"), ("microstructure_liquidity_timing",)),
    fd("microstructure_pressure_score", "microstructure pressure score", "high", 0.75, "microstructure", "max(ofi_filled + depth_imbalance_filled + price_momentum - spread_filled, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("clob_features",), ("microstructure_liquidity_timing",)),
    fd("microstructure_pressure_edge", "microstructure pressure edge", "high", 0.75, "microstructure", "max(entry_forward_edge, 0) * microstructure_pressure_score", "features.reverse_engineering._add_cross_category_edge_factors", None, ("clob_features", "fills"), ("microstructure_liquidity_timing",)),
    fd("trade_notional", "ticket size", "high", 0.75, "basic", "shares * price", "features.basic.add_basic_factors", None, ("fills",)),
    fd("time_to_resolution_secs", "time to resolution", "high", 0.50, "timing", "(resolution_time - fill timestamp) in seconds", "pipeline.build_factor_table", None, ("markets",), ("settlement_timing",)),
    fd("pre_news_lag_secs", "pre-news timing", "low", 0.25, "news", "(fill timestamp - latest news published_at) in seconds", "features.timing.add_timing_factors", None, ("news",), ("event_news_information_edge",)),
    fd("entry_hour_utc", "entry hour UTC", "low", 0.50, "timing", "UTC hour extracted from fill timestamp", "features.timing.add_timing_factors", None, ("fills",)),
    fd("nwp_node_lag_secs", "NWP model-node lag", "low", 0.25, "weather_timing", "seconds since latest 00Z/06Z/12Z/18Z model node", "features.timing.add_timing_factors", None, ("fills",), ("weather_temperature",)),
    fd("late_day_temperature_nowcast_edge", "late-day temperature nowcast window", "high", 0.50, "weather_timing", "1 when entry hour is between 18 and 22 UTC, else 0", "features.timing.add_timing_factors", None, ("fills",), ("weather_temperature",)),
    fd("is_last_24h", "last 24h entry", "high", 0.50, "settlement_timing", "1 when time_to_resolution_secs <= 86400, else 0", "features.timing.add_timing_factors", None, ("markets",), ("settlement_timing",)),
    fd("is_last_6h", "last 6h entry", "high", 0.50, "settlement_timing", "1 when time_to_resolution_secs <= 21600, else 0", "features.timing.add_timing_factors", None, ("markets",), ("settlement_timing",)),
    fd("settlement_window_edge", "settlement window edge", "high", 0.75, "settlement_timing", "is_last_24h * max(entry_forward_edge, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets", "fills"), ("settlement_timing",)),
    fd("settlement_urgency_edge", "settlement urgency edge", "high", 0.75, "settlement_timing", "is_last_24h * max(entry_forward_edge, 0) / (1 + resolution_lead_time_hours)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets", "fills"), ("settlement_timing",)),
    fd("same_market_reentry_count", "same-market reentry count", "high", 0.75, "behavior", "count rows over account + market_id", "features.behavior.add_behavior_factors", None, ("fills",)),
    fd("buy_ratio", "wallet buy-side ratio", "high", 0.50, "behavior", "mean(side == buy) over account", "features.behavior.add_behavior_factors", None, ("fills",)),
    fd("forward_price_move", "next market price move", "high", 0.50, "reverse_engineering", "next market fill price - current fill price after sorting by market_id,timestamp", "features.reverse_engineering._add_forward_move_factors", None, ("fills",)),
    fd("entry_forward_edge", "directional entry edge", "high", 0.75, "reverse_engineering", "buy: next price - price; sell: price - next price", "features.reverse_engineering._add_forward_move_factors", None, ("fills",)),
    fd("entry_before_move_secs", "entry before favorable move", "low", 0.50, "reverse_engineering", "seconds to next market fill when entry_forward_edge > 0", "features.reverse_engineering._add_forward_move_factors", None, ("fills",), ("event_news_information_edge",)),
    fd("lead_time_evidence", "entry lead-time evidence", "high", 0.75, "reverse_engineering", "entry_forward_edge / (1 + next_lag_hours) when next_lag_secs > 0", "features.reverse_engineering._add_forward_move_factors", None, ("fills",), ("event_news_information_edge",)),
    fd("entry_price_advantage", "entry price advantage", "high", 0.75, "reverse_engineering", "for buys, market mean price - fill price", "features.reverse_engineering._add_exit_quality_factors", None, ("fills",)),
    fd("exit_quality_proxy", "exit quality proxy", "high", 0.75, "reverse_engineering", "for sells, sell price - wallet average buy price in same market", "features.reverse_engineering._add_exit_quality_factors", None, ("fills",), ("settlement_timing",)),
    fd("sector_concentration", "sector concentration", "high", 0.75, "sector", "count(account, sector) / count(account)", "features.reverse_engineering._add_sector_factors", None, ("markets",), ("sector_information_edge", "cross_sector_scanner")),
    fd("sector_trade_count", "sector trade count", "high", 0.75, "sector", "count rows over account + sector", "features.reverse_engineering._add_sector_factors", None, ("markets",), ("sector_information_edge",)),
    fd("sector_pnl_proxy", "sector PnL proxy", "high", 0.75, "sector", "sum signed notional over account + sector; buy negative, sell positive", "features.reverse_engineering._add_sector_factors", None, ("markets",), ("sector_information_edge",)),
    fd("sector_entry_edge", "sector entry edge", "high", 0.75, "sector", "mean(entry_forward_edge) over account + sector", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets", "fills"), ("sector_information_edge",)),
    fd("sector_repeat_edge_score", "sector repeat edge score", "high", 0.75, "sector", "sector_concentration * max(entry_forward_edge, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets", "fills"), ("sector_information_edge",)),
    fd("sector_motif_consistency_edge", "sector motif consistency edge", "high", 0.75, "sector", "sector_concentration * repeat_hour_motif_score * max(entry_forward_edge, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets", "fills"), ("sector_information_edge", "cross_sector_scanner")),
    fd("cross_sector_breadth", "cross-sector breadth", "high", 0.50, "sector", "clip(1 - sector_concentration, 0, 1)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("markets",), ("cross_sector_scanner",)),
    fd("resolution_lead_time_hours", "resolution lead time hours", "high", 0.50, "settlement_timing", "time_to_resolution_secs / 3600", "features.reverse_engineering._add_lead_time_factors", None, ("markets",), ("settlement_timing",)),
    fd("news_recency_hours", "news recency hours", "low", 0.25, "news", "pre_news_lag_secs / 3600", "features.reverse_engineering._add_lead_time_factors", None, ("news",), ("event_news_information_edge",)),
    fd("news_reaction_window", "news reaction window", "high", 0.50, "news", "1 when 0 <= pre_news_lag_secs <= 21600, else 0", "features.reverse_engineering._add_lead_time_factors", None, ("news",), ("event_news_information_edge",)),
    fd("news_lead_entry_edge", "news lead-entry edge", "high", 0.75, "news", "news_reaction_window * max(entry_forward_edge, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("news", "fills"), ("event_news_information_edge",)),
    fd("news_recency_decay_edge", "news recency decay edge", "high", 0.75, "news", "max(entry_forward_edge, 0) / (1 + news_recency_hours)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("news", "fills"), ("event_news_information_edge",)),
    fd("repeat_hour_motif_score", "repeat hour motif score", "high", 0.75, "motif", "count(account, entry_hour_utc) / count(account)", "features.reverse_engineering._add_repeated_motif_factors", None, ("fills",)),
    fd("repeat_entry_motif_count", "repeat entry motif count", "high", 0.75, "motif", "count(account, market_id, side, entry_hour_utc)", "features.reverse_engineering._add_repeated_motif_factors", None, ("fills",)),
    fd("repeat_market_add_rate", "repeat market add rate", "high", 0.75, "motif", "same_market_reentry_count / count(account)", "features.reverse_engineering._add_repeated_motif_factors", None, ("fills",)),
    fd("event_motif_recurrence", "event motif recurrence", "high", 0.75, "motif", "repeat_hour_motif_score * repeat_entry_motif_count * max(entry_forward_edge, 0)", "features.reverse_engineering._add_cross_category_edge_factors", None, ("fills",), ("sector_information_edge", "event_news_information_edge", "cross_sector_scanner")),
    fd("is_weather_market", "weather market specialization", "high", 0.50, "weather_semantic", "1 when slug/title/outcome parses as weather temperature market, else 0", "features.weather.add_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("weather_market_ratio", "weather trader specialization", "high", 0.50, "weather_semantic", "mean(is_weather_market) over account", "features.weather._add_account_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("weather_city_concentration", "weather city concentration", "high", 0.75, "weather_semantic", "count(account, weather_city) / count(account)", "features.weather._add_account_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("weather_market_breadth", "weather market breadth", "high", 0.50, "weather_semantic", "n_unique weather market_id over account", "features.weather._add_account_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("weather_city_count", "weather city breadth", "high", 0.50, "weather_semantic", "n_unique weather_city over account", "features.weather._add_account_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("temperature_mid_f", "temperature bucket midpoint", "high", 0.50, "weather_semantic", "(temperature_low_f + temperature_high_f) / 2 when both bounds exist", "features.weather._parse_row", None, ("fills",), ("weather_temperature",)),
    fd("temperature_bucket_width_f", "temperature bucket width", "low", 0.50, "weather_semantic", "temperature_high_f - temperature_low_f when both bounds exist", "features.weather._parse_row", None, ("fills",), ("weather_temperature",)),
    fd("is_low_temp_bucket", "low-temperature bucket", "high", 0.50, "weather_semantic", "1 when parsed bucket anchor <= 40F, else 0", "features.weather._parse_row", None, ("fills",), ("weather_temperature",)),
    fd("is_high_temp_bucket", "high-temperature bucket", "high", 0.50, "weather_semantic", "1 when parsed bucket anchor >= 75F, else 0", "features.weather._parse_row", None, ("fills",), ("weather_temperature",)),
    fd("is_extreme_temperature_bucket", "extreme-temperature bucket", "high", 0.50, "weather_semantic", "1 when bucket anchor <= 32F or >= 90F, else 0", "features.weather._parse_row", None, ("fills",), ("weather_temperature",)),
    fd("weather_low_price_bucket_value", "low-price weather bucket value", "high", 0.50, "weather_semantic", "1 when weather market, price < 0.20, and temperature bucket exists", "features.weather.add_weather_factors", None, ("fills",), ("weather_temperature",)),
    fd("official_station_source_available", "official station source available", "high", 0.50, "weather_official", "1 when weather market has official_station_id or resolution_source metadata", "features.weather._add_weather_event_context_factors", None, ("weather_events",), ("weather_temperature",)),
    fd("official_station_basis", "official station basis", "low", 0.50, "weather_official", "official_high_temp_f - actual_high_temp_f", "features.weather._add_weather_event_context_factors", None, ("weather_events", "weather_observations"), ("weather_temperature",)),
    fd("official_station_bucket_distance", "official station bucket distance", "low", 0.50, "weather_official", "distance from official_high_to_date_f to parsed bucket; 0 when inside", "features.weather._add_official_station_target_factors", None, ("weather_events", "official_weather"), ("weather_temperature",)),
    fd("official_station_inside_bucket_now", "official station inside bucket now", "high", 0.50, "weather_official", "1 when official_high_to_date_f is inside parsed bucket, else 0", "features.weather._add_official_station_target_factors", None, ("weather_events", "official_weather"), ("weather_temperature",)),
    fd("official_station_target_bucket_edge", "official station target bucket edge", "high", 0.75, "weather_official", "(1 / (1 + official_station_bucket_distance)) * (1 - price) + ladder_mispricing", "features.weather._add_official_station_target_factors", None, ("weather_events", "official_weather"), ("weather_temperature",)),
    fd("temperature_bucket_ladder_mispricing", "temperature bucket ladder mispricing", "high", 0.75, "weather_ladder", "abs(fill price - ladder_yes_price) for open sibling bucket markets", "features.weather._add_weather_event_context_factors", None, ("weather_events",), ("weather_temperature",)),
    fd("actual_temp_distance_to_bucket", "actual temp distance to bucket", "low", 0.50, "weather_observation", "distance from actual_high_temp_f to parsed bucket; 0 when inside", "features.weather_observations.add_weather_observation_factors", None, ("weather_observations",), ("weather_temperature",)),
    fd("actual_temp_inside_bucket", "actual temp inside bucket", "high", 0.50, "weather_observation", "1 when actual_high_temp_f is inside parsed bucket, else 0", "features.weather_observations.add_weather_observation_factors", None, ("weather_observations",), ("weather_temperature",)),
    fd("actual_temp_error_to_mid_f", "actual temp error to midpoint", "low", 0.50, "weather_observation", "actual_high_temp_f - temperature_mid_f", "features.weather_observations.add_weather_observation_factors", None, ("weather_observations",), ("weather_temperature",)),
    fd("forecast_temp_f", "historical forecast temperature", "high", 0.50, "weather_forecast", "as-of mean forecast temperature from forecast history joined within 6h", "pipeline.attach_weather_forecasts", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_error_to_bucket", "forecast distance to bucket", "low", 0.50, "weather_forecast", "distance from forecast_temp_f to parsed bucket; 0 when inside", "features.weather_forecasts.add_weather_forecast_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_inside_bucket", "forecast inside bucket", "high", 0.50, "weather_forecast", "1 when forecast_temp_f is inside parsed bucket, else 0", "features.weather_forecasts.add_weather_forecast_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_delta_1h", "forecast 1h revision", "high", 0.75, "weather_forecast", "diff(forecast_temp_f) over weather_city sorted by timestamp", "features.weather_forecasts.add_weather_forecast_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_delta_6h", "forecast 6h revision", "high", 0.75, "weather_forecast", "forecast_temp_f - forecast_temp_f.shift(6) over weather_city", "features.weather_forecasts.add_weather_forecast_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_volatility", "forecast short-window volatility", "high", 0.75, "weather_forecast", "rolling_std(forecast_temp_f, 6) over weather_city", "features.weather_forecasts.add_weather_forecast_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_model_count", "forecast model/source count", "high", 0.50, "weather_forecast", "n_unique forecast_source per city+forecast_timestamp", "pipeline.attach_weather_forecasts", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("model_disagreement", "forecast model disagreement", "high", 0.75, "weather_forecast", "forecast_model_range_f, or forecast_model_std_f * 2 when range is unavailable", "features.weather_forecasts._add_multi_model_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("forecast_bias_error_f", "forecast realized bias error", "high", 0.50, "weather_forecast", "official_high_temp_f or actual_high_temp_f minus forecast_temp_f", "features.weather_forecasts._add_city_bias_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("city_temperature_bias_edge", "city temperature bias edge", "high", 0.75, "weather_forecast", "abs(mean(forecast_bias_error_f) over weather_city)", "features.weather_forecasts._add_city_bias_factors", None, ("weather_forecasts",), ("weather_temperature",)),
    fd("bucket_distance_from_normal", "bucket distance from city normal", "high", 0.75, "weather_forecast", "abs(temperature_mid_f - median(forecast_temp_f) over weather_city)", "features.weather_forecasts._add_bucket_normal_factors", None, ("weather_forecasts",), ("weather_temperature",)),
]


def factor_definition(column: str) -> FactorDefinition | None:
    return FACTOR_DEFINITIONS_BY_COLUMN.get(column)


def factor_definitions_by_category(category: str | None = None) -> dict[str, list[FactorDefinition]]:
    groups: dict[str, list[FactorDefinition]] = {}
    for definition in _filter_category(FACTOR_DEFINITIONS, category):
        groups.setdefault(definition.category, []).append(definition)
    return groups


def factor_catalog_rows(category: str | None = None) -> list[dict]:
    return [definition.to_dict() for definition in _filter_category(FACTOR_DEFINITIONS, category)]


def _filter_category(
    definitions: Iterable[FactorDefinition],
    category: str | None,
) -> list[FactorDefinition]:
    if not category:
        return list(definitions)
    return [
        definition
        for definition in definitions
        if definition.category == category or category in definition.playbooks
    ]


FACTOR_DEFINITIONS_BY_COLUMN = {definition.column: definition for definition in FACTOR_DEFINITIONS}
