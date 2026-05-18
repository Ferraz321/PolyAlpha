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
]


WEATHER_CANDIDATE_FACTORS = [
    "forecast_temp_f",
    "forecast_error_to_bucket",
    "forecast_inside_bucket",
    "forecast_delta_1h",
    "forecast_delta_6h",
    "forecast_volatility",
    "model_disagreement",
    "actual_temp_distance_to_bucket",
    "bucket_distance_from_normal",
    "city_specific_win_rate",
    "city_specific_pnl",
    "weather_realized_pnl",
    "weather_expectancy",
    "max_weather_market_pnl_share",
]


def infer_market_categories(wallet: dict) -> list[dict]:
    distributions = wallet.get("distributions", {})
    ratio = _p50(distributions, "weather_market_ratio")
    if ratio < 0.5:
        return []
    available = [
        factor
        for factor in WEATHER_ACTIVE_FACTORS
        if distributions.get(factor, {}).get("count", 0) > 0
    ]
    missing = [factor for factor in WEATHER_ACTIVE_FACTORS if factor not in available]
    available_set = set(available)
    next_candidates = [
        factor
        for factor in WEATHER_CANDIDATE_FACTORS
        if factor not in available_set
    ]
    return [
        {
            "id": "weather_temperature",
            "label": "weather temperature specialist",
            "confidence": min(1.0, ratio),
            "active_factors": available,
            "missing_active_factors": missing,
            "next_candidate_factors": next_candidates,
            "summary": _weather_summary(distributions),
        }
    ]


def _weather_summary(distributions: dict) -> str:
    ratio = _p50(distributions, "weather_market_ratio")
    breadth = _p50(distributions, "weather_market_breadth")
    cities = _p50(distributions, "weather_city_count")
    width = _p50(distributions, "temperature_bucket_width_f")
    return (
        f"weather_ratio={ratio:.2%}; markets={breadth:.0f}; "
        f"cities={cities:.0f}; median_bucket_width={width:.2f}F"
    )


def _p50(distributions: dict, factor: str) -> float:
    value = distributions.get(factor, {}).get("p50", 0.0)
    return float(value or 0.0)
