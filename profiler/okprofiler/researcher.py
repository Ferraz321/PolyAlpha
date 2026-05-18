import polars as pl

from .statistics import numeric, quantile, spike_zscore


def research_note(wallet: pl.DataFrame, mining: dict) -> dict:
    best = mining.get("best_rule", {})
    ofi = numeric(wallet, "ofi_filled")
    spread = numeric(wallet, "spread_filled")
    depth = numeric(wallet, "depth_imbalance_filled")
    distinct_markets = wallet.get_column("market_id").n_unique()
    archetype = _archetype(wallet, distinct_markets, ofi, spread, depth)
    return {
        "archetype": archetype,
        "summary": (
            f"{archetype}; best_rule={best.get('name')}; "
            f"score={best.get('score', 0.0):.2f}; coverage={best.get('coverage', 0.0):.2%}; "
            f"precision_proxy={best.get('precision_proxy', 0.0):.2%}"
        ),
        "next_experiments": _next_experiments(wallet, best, distinct_markets),
        "caveats": _caveats(wallet, best),
    }


def _archetype(
    wallet: pl.DataFrame,
    distinct_markets: int,
    ofi,
    spread,
    depth,
) -> str:
    weather_ratio = quantile(numeric(wallet, "weather_market_ratio"), 0.50)
    if weather_ratio >= 0.5:
        return "weather-temperature specialist candidate"
    if distinct_markets <= 3 and spike_zscore(ofi) > 2.0:
        return "information-edge candidate"
    if wallet.height >= 1000 and quantile(spread, 0.50) <= 0.02:
        return "market-making or stat-arb candidate"
    if spike_zscore(depth) > 2.0:
        return "liquidity-imbalance timing candidate"
    if distinct_markets >= 10:
        return "cross-market alpha candidate"
    return "mixed alpha candidate"


def _next_experiments(wallet: pl.DataFrame, best: dict, distinct_markets: int) -> list[str]:
    experiments = []
    if quantile(numeric(wallet, "weather_market_ratio"), 0.50) >= 0.5:
        experiments.extend(
            [
                "join NOAA/Open-Meteo forecasts and compute forecast_error_to_bucket",
                "split weather trades by city to measure city-specific edge",
                "compare entry time against forecast update windows and market resolution",
            ]
        )
    if "time_to_resolution_secs" not in [c.get("column") for c in best.get("conditions", [])]:
        experiments.append("add time-to-resolution buckets and compare early vs late entries")
    if distinct_markets <= 5:
        experiments.append("add sector/news labels to test whether edge is event-specific")
    if wallet.height >= 50:
        experiments.append("split sample by time and verify factor thresholds are stable")
    experiments.append("add negative controls from non-wallet fills for true precision/recall")
    return experiments


def _caveats(wallet: pl.DataFrame, best: dict) -> list[str]:
    caveats = []
    if wallet.height < 30:
        caveats.append("sample size is still thin; treat all thresholds as provisional")
    if best.get("coverage", 0.0) < 0.2:
        caveats.append("best rule explains only a small fraction of wallet fills")
    if best.get("factor_stability", 0.0) < 0.4:
        caveats.append("factor threshold drifts across the sample")
    return caveats
