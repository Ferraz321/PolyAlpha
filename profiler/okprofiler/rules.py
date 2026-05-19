import polars as pl

from .market_categories import infer_market_categories
from .miner import mine_wallet
from .researcher import research_note
from .statistics import distribution, numeric
from .strategy import strategy_config_from_rules


PROFILE_COLUMNS = [
    "ofi_filled",
    "spread_filled",
    "price_momentum",
    "depth_imbalance_filled",
    "time_to_resolution_secs",
    "feature_lag_secs",
    "trade_notional",
    "abs_price_momentum",
    "entry_hour_utc",
    "is_last_24h",
    "is_last_6h",
    "same_market_reentry_count",
    "buy_ratio",
    "forward_price_move",
    "entry_forward_edge",
    "entry_before_move_secs",
    "lead_time_evidence",
    "entry_price_advantage",
    "exit_quality_proxy",
    "sector_concentration",
    "sector_trade_count",
    "sector_pnl_proxy",
    "sector_entry_edge",
    "sector_repeat_edge_score",
    "cross_sector_breadth",
    "resolution_lead_time_hours",
    "settlement_window_edge",
    "news_recency_hours",
    "news_reaction_window",
    "news_lead_entry_edge",
    "microstructure_entry_edge",
    "repeat_hour_motif_score",
    "repeat_entry_motif_count",
    "repeat_market_add_rate",
    "event_motif_recurrence",
    "is_weather_market",
    "weather_market_ratio",
    "weather_city_concentration",
    "weather_market_breadth",
    "weather_city_count",
    "temperature_mid_f",
    "temperature_bucket_width_f",
    "is_low_temp_bucket",
    "is_high_temp_bucket",
    "is_extreme_temperature_bucket",
    "actual_temp_distance_to_bucket",
    "actual_temp_inside_bucket",
    "actual_temp_error_to_mid_f",
    "forecast_temp_f",
    "forecast_error_to_bucket",
    "forecast_inside_bucket",
    "forecast_delta_1h",
    "forecast_delta_6h",
    "forecast_volatility",
    "forecast_model_count",
    "model_disagreement",
    "forecast_bias_error_f",
    "city_temperature_bias_edge",
    "bucket_distance_from_normal",
    "official_station_bucket_distance",
    "official_station_inside_bucket_now",
    "official_station_target_bucket_edge",
    "official_station_basis",
    "temperature_bucket_ladder_mispricing",
]


def infer_wallet_rules(
    joined: pl.DataFrame,
    min_samples: int,
    disabled_factors: set[str] | None = None,
) -> dict:
    wallets = []
    for account in joined.get_column("account").unique().to_list():
        wallet = joined.filter(pl.col("account") == account)
        if wallet.height < min_samples:
            wallets.append(_small_sample(account, wallet.height))
            continue
        wallets.append(_wallet_rule(account, wallet, disabled_factors or set()))
    return {"version": 1, "rows": joined.height, "wallets": wallets}


def _wallet_rule(account: str, wallet: pl.DataFrame, disabled_factors: set[str]) -> dict:
    mining = mine_wallet(wallet, disabled_factors=disabled_factors)
    researcher = research_note(wallet, mining)
    buy = wallet.filter(pl.col("side").str.to_lowercase() == "buy")
    sell = wallet.filter(pl.col("side").str.to_lowercase() == "sell")
    result = {
        "account": account,
        "samples": wallet.height,
        "buy_samples": buy.height,
        "sell_samples": sell.height,
        "distributions": _distributions(wallet),
        "mining": mining,
        "candidate_rule": _candidate_rule(mining),
        "backtest": _backtest_from_mining(mining),
        "explainability_score": _explainability_score(mining),
        "agent_research_note": researcher["summary"],
        "researcher": researcher,
    }
    result["market_categories"] = infer_market_categories(result)
    return result


def _distributions(wallet: pl.DataFrame) -> dict:
    return {
        column: distribution(numeric(wallet, column))
        for column in PROFILE_COLUMNS
        if column in wallet.columns
    }


def _candidate_rule(mining: dict) -> str:
    best = mining.get("best_rule", {})
    parts = []
    for condition in best.get("conditions", []):
        parts.append(
            f"{condition['column']} {condition['op']} {condition['value']:.6f}"
        )
    return "trigger when " + " and ".join(parts) if parts else "no candidate rule"


def _backtest_from_mining(mining: dict) -> dict:
    best = mining.get("best_rule", {})
    return {
        "samples": best.get("samples", 0),
        "hits": best.get("hits", 0),
        "coverage": best.get("coverage", 0.0),
        "precision_proxy": best.get("precision_proxy", 0.0),
        "recall_proxy": best.get("recall_proxy", 0.0),
        "factor_stability": best.get("factor_stability", 0.0),
        "reproducibility_score": best.get("score", 0.0),
    }


def _explainability_score(mining: dict) -> float:
    best = mining.get("best_rule", {})
    return float(best.get("score", 0.0))


def _small_sample(account: str, samples: int) -> dict:
    return {
        "account": account,
        "samples": samples,
        "status": "small_sample",
        "candidate_rule": "collect more observations before inferring thresholds",
    }
