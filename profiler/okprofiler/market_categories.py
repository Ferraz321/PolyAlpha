WEATHER_ACTIVE_FACTORS = [
    "weather_market_ratio",
    "weather_market_breadth",
    "weather_city_count",
    "weather_city_concentration",
    "temperature_mid_f",
    "temperature_bucket_width_f",
    "is_low_temp_bucket",
    "is_high_temp_bucket",
    "is_extreme_temperature_bucket",
    "entry_hour_utc",
    "is_last_24h",
    "is_last_6h",
    "trade_notional",
    "same_market_reentry_count",
    "buy_ratio",
    "actual_temp_distance_to_bucket",
    "actual_temp_inside_bucket",
    "actual_temp_error_to_mid_f",
    "forecast_temp_f",
    "forecast_error_to_bucket",
    "forecast_inside_bucket",
    "forecast_delta_1h",
    "forecast_delta_6h",
    "forecast_volatility",
]


WEATHER_CANDIDATE_FACTORS = [
    "model_disagreement",
    "actual_temp_distance_to_bucket",
    "bucket_distance_from_normal",
    "city_specific_win_rate",
    "city_specific_pnl",
    "weather_realized_pnl",
    "weather_expectancy",
    "max_weather_market_pnl_share",
]


SECTOR_ACTIVE_FACTORS = [
    "sector_concentration",
    "sector_trade_count",
    "sector_pnl_proxy",
    "sector_entry_edge",
    "sector_repeat_edge_score",
    "cross_sector_breadth",
    "entry_forward_edge",
    "entry_price_advantage",
    "repeat_entry_motif_count",
]


SECTOR_CANDIDATE_FACTORS = [
    "sector_entry_edge",
    "sector_repeat_edge_score",
    "cross_sector_breadth",
    "event_motif_recurrence",
    "sector_pnl_proxy",
]


NEWS_ACTIVE_FACTORS = [
    "pre_news_lag_secs",
    "news_recency_hours",
    "news_reaction_window",
    "news_lead_entry_edge",
    "entry_before_move_secs",
    "lead_time_evidence",
    "entry_forward_edge",
]


NEWS_CANDIDATE_FACTORS = [
    "news_lead_entry_edge",
    "lead_time_evidence",
    "entry_before_move_secs",
    "event_motif_recurrence",
]


MICROSTRUCTURE_ACTIVE_FACTORS = [
    "ofi_filled",
    "spread_filled",
    "depth_imbalance_filled",
    "price_momentum",
    "abs_price_momentum",
    "feature_lag_secs",
    "distance_to_bid",
    "distance_to_ask",
    "microstructure_entry_edge",
]


MICROSTRUCTURE_CANDIDATE_FACTORS = [
    "microstructure_entry_edge",
    "spread_filled",
    "depth_imbalance_filled",
    "price_momentum",
    "strategy_capacity_usd",
    "exit_fillability",
]


SETTLEMENT_ACTIVE_FACTORS = [
    "time_to_resolution_secs",
    "resolution_lead_time_hours",
    "is_last_24h",
    "is_last_6h",
    "settlement_window_edge",
    "entry_forward_edge",
    "exit_quality_proxy",
]


SETTLEMENT_CANDIDATE_FACTORS = [
    "settlement_window_edge",
    "is_last_6h",
    "exit_quality_proxy",
    "strategy_capacity_usd",
]


def infer_market_categories(wallet: dict) -> list[dict]:
    distributions = wallet.get("distributions", {})
    categories = []
    weather = _weather_category(distributions)
    if weather:
        categories.append(weather)
    for builder in [
        _sector_information_category,
        _news_information_category,
        _microstructure_category,
        _settlement_timing_category,
        _cross_sector_scanner_category,
    ]:
        category = builder(distributions)
        if category:
            categories.append(category)
    return categories


def _weather_category(distributions: dict) -> dict | None:
    ratio = _p50(distributions, "weather_market_ratio")
    if ratio < 0.5:
        return None
    return _category(
        "weather_temperature",
        "weather temperature specialist",
        min(1.0, ratio),
        WEATHER_ACTIVE_FACTORS,
        WEATHER_CANDIDATE_FACTORS,
        distributions,
        _weather_summary(distributions),
    )


def _sector_information_category(distributions: dict) -> dict | None:
    concentration = _p50(distributions, "sector_concentration")
    trades = _p50(distributions, "sector_trade_count")
    edge = _p50(distributions, "sector_entry_edge")
    if concentration < 0.55 and trades < 5:
        return None
    confidence = min(1.0, 0.45 + concentration * 0.35 + min(trades / 50.0, 0.20))
    if edge > 0:
        confidence = min(1.0, confidence + 0.10)
    return _category(
        "sector_information_edge",
        "sector information edge",
        confidence,
        SECTOR_ACTIVE_FACTORS,
        SECTOR_CANDIDATE_FACTORS,
        distributions,
        (
            f"sector_concentration={concentration:.2%}; "
            f"sector_trades={trades:.0f}; sector_entry_edge={edge:.4f}"
        ),
    )


def _news_information_category(distributions: dict) -> dict | None:
    reaction = _p50(distributions, "news_reaction_window")
    recency = _p50(distributions, "news_recency_hours")
    lead_edge = _p50(distributions, "news_lead_entry_edge")
    if reaction < 0.20 and (recency <= 0.0 or recency > 12.0):
        return None
    confidence = min(1.0, 0.35 + reaction * 0.45 + max(0.0, 12.0 - recency) / 12.0 * 0.15)
    if lead_edge > 0:
        confidence = min(1.0, confidence + 0.10)
    return _category(
        "event_news_information_edge",
        "event/news information edge",
        confidence,
        NEWS_ACTIVE_FACTORS,
        NEWS_CANDIDATE_FACTORS,
        distributions,
        (
            f"news_reaction_window={reaction:.2%}; "
            f"median_news_recency={recency:.2f}h; news_lead_edge={lead_edge:.4f}"
        ),
    )


def _microstructure_category(distributions: dict) -> dict | None:
    available = _available(MICROSTRUCTURE_ACTIVE_FACTORS, distributions)
    if len(available) < 2:
        return None
    ofi = abs(_p90(distributions, "ofi_filled"))
    depth = abs(_p90(distributions, "depth_imbalance_filled"))
    momentum = abs(_p90(distributions, "price_momentum"))
    confidence = min(1.0, 0.35 + min(len(available) / 10.0, 0.35) + min(ofi + depth + momentum, 0.30))
    return _category(
        "microstructure_liquidity_timing",
        "microstructure/liquidity timing",
        confidence,
        MICROSTRUCTURE_ACTIVE_FACTORS,
        MICROSTRUCTURE_CANDIDATE_FACTORS,
        distributions,
        (
            f"clob_factors={len(available)}; "
            f"ofi_p90={ofi:.4f}; depth_p90={depth:.4f}; momentum_p90={momentum:.4f}"
        ),
    )


def _settlement_timing_category(distributions: dict) -> dict | None:
    last_24h = _p50(distributions, "is_last_24h")
    last_6h = _p50(distributions, "is_last_6h")
    window_edge = _p50(distributions, "settlement_window_edge")
    if last_24h < 0.20 and last_6h < 0.05:
        return None
    confidence = min(1.0, 0.35 + last_24h * 0.35 + last_6h * 0.20)
    if window_edge > 0:
        confidence = min(1.0, confidence + 0.10)
    return _category(
        "settlement_timing",
        "settlement timing specialist",
        confidence,
        SETTLEMENT_ACTIVE_FACTORS,
        SETTLEMENT_CANDIDATE_FACTORS,
        distributions,
        (
            f"last_24h={last_24h:.2%}; last_6h={last_6h:.2%}; "
            f"settlement_window_edge={window_edge:.4f}"
        ),
    )


def _cross_sector_scanner_category(distributions: dict) -> dict | None:
    breadth = _p50(distributions, "cross_sector_breadth")
    concentration = _p50(distributions, "sector_concentration")
    if breadth < 0.45 or concentration > 0.65:
        return None
    confidence = min(1.0, 0.40 + breadth * 0.45)
    return _category(
        "cross_sector_scanner",
        "cross-sector scanner",
        confidence,
        SECTOR_ACTIVE_FACTORS,
        ["cross_sector_breadth", "lead_time_evidence", "event_motif_recurrence"],
        distributions,
        f"cross_sector_breadth={breadth:.2%}; sector_concentration={concentration:.2%}",
    )


def _category(
    category_id: str,
    label: str,
    confidence: float,
    active_factors: list[str],
    candidate_factors: list[str],
    distributions: dict,
    summary: str,
) -> dict:
    available = _available(active_factors, distributions)
    available_set = set(available)
    return {
        "id": category_id,
        "label": label,
        "confidence": round(float(confidence), 4),
        "active_factors": available,
        "missing_active_factors": [factor for factor in active_factors if factor not in available_set],
        "next_candidate_factors": [
            factor for factor in candidate_factors if factor not in available_set
        ],
        "summary": summary,
    }


def _weather_summary(distributions: dict) -> str:
    ratio = _p50(distributions, "weather_market_ratio")
    breadth = _p50(distributions, "weather_market_breadth")
    cities = _p50(distributions, "weather_city_count")
    width = _p50(distributions, "temperature_bucket_width_f")
    return (
        f"weather_ratio={ratio:.2%}; markets={breadth:.0f}; "
        f"cities={cities:.0f}; median_bucket_width={width:.2f}F"
    )


def _available(factors: list[str], distributions: dict) -> list[str]:
    return [factor for factor in factors if distributions.get(factor, {}).get("count", 0) > 0]


def _p50(distributions: dict, factor: str) -> float:
    value = distributions.get(factor, {}).get("p50", 0.0)
    return float(value or 0.0)


def _p90(distributions: dict, factor: str) -> float:
    value = distributions.get(factor, {}).get("p90", 0.0)
    return float(value or 0.0)
