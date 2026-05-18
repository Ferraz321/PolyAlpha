import numpy as np
import polars as pl
import json
from sklearn.neighbors import KernelDensity


def infer_wallet_rules(joined: pl.DataFrame, min_samples: int) -> dict:
    wallets = []
    for account in joined.get_column("account").unique().to_list():
        wallet = joined.filter(pl.col("account") == account)
        if wallet.height < min_samples:
            wallets.append(_small_sample(account, wallet.height))
            continue
        wallets.append(_wallet_rule(account, wallet))
    return {
        "version": 1,
        "rows": joined.height,
        "wallets": wallets,
    }


def strategy_config_from_rules(rules: dict) -> str:
    strategies = []
    for wallet in rules.get("wallets", []):
        if wallet.get("status") == "small_sample":
            continue
        ofi_threshold = wallet.get("ofi", {}).get("p90", 0.0)
        spread_threshold = wallet.get("spread", {}).get("p50", 0.0)
        momentum_threshold = wallet.get("price_momentum", {}).get("p50", 0.0)
        depth_threshold = wallet.get("depth_imbalance", {}).get("p50", 0.0)
        strategies.append(
            {
                "id": f"reverse_{wallet['account'][:10]}",
                "source_wallet": wallet["account"],
                "enabled": False,
                "trigger": {
                    "all": [
                        {"feature": "ofi", "op": ">", "value": ofi_threshold},
                        {"feature": "spread", "op": "<=", "value": spread_threshold},
                        {
                            "feature": "price_momentum",
                            "op": ">=",
                            "value": momentum_threshold,
                        },
                        {
                            "feature": "depth_imbalance",
                            "op": ">=",
                            "value": depth_threshold,
                        },
                    ]
                },
                "risk": {
                    "mode": "alert_only",
                    "max_notional_usd": 0,
                },
            }
        )
    return json.dumps({"version": 1, "strategies": strategies}, indent=2)


def _wallet_rule(account: str, wallet: pl.DataFrame) -> dict:
    ofi = _numeric(wallet, "ofi")
    spread = _numeric(wallet, "spread")
    momentum = _numeric(wallet, "price_momentum")
    depth = _numeric(wallet, "depth_imbalance_filled")
    time_to_resolution = _numeric(wallet, "time_to_resolution_secs")
    lag = _numeric(wallet, "feature_lag_secs")
    buy = wallet.filter(pl.col("side").str.to_lowercase() == "buy")
    sell = wallet.filter(pl.col("side").str.to_lowercase() == "sell")
    backtest = _backtest(wallet, ofi, spread, momentum, depth)
    return {
        "account": account,
        "samples": wallet.height,
        "buy_samples": buy.height,
        "sell_samples": sell.height,
        "ofi": _distribution(ofi),
        "spread": _distribution(spread),
        "price_momentum": _distribution(momentum),
        "depth_imbalance": _distribution(depth),
        "time_to_resolution_secs": _distribution(time_to_resolution),
        "feature_lag_secs": _distribution(lag),
        "candidate_rule": _candidate_rule(ofi, spread, momentum, depth),
        "backtest": backtest,
        "explainability_score": _explainability_score(ofi, spread, momentum, depth, backtest),
        "agent_research_note": _research_note(wallet, backtest, ofi, spread, depth),
    }


def _small_sample(account: str, samples: int) -> dict:
    return {
        "account": account,
        "samples": samples,
        "status": "small_sample",
        "candidate_rule": "collect more observations before inferring thresholds",
    }


def _candidate_rule(
    ofi: np.ndarray,
    spread: np.ndarray,
    momentum: np.ndarray,
    depth: np.ndarray,
) -> str:
    ofi_p90 = _quantile(ofi, 0.90)
    spread_p50 = _quantile(spread, 0.50)
    momentum_p50 = _quantile(momentum, 0.50)
    depth_p50 = _quantile(depth, 0.50)
    return (
        f"trigger when ofi > {ofi_p90:.6f}, spread <= {spread_p50:.6f}, "
        f"price_momentum >= {momentum_p50:.6f}, depth_imbalance >= {depth_p50:.6f}"
    )


def _distribution(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "p10": _quantile(values, 0.10),
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "kde_mode": _kde_mode(values) if len(values) >= 5 else _quantile(values, 0.50),
        "spike_zscore": _spike_zscore(values),
    }


def _numeric(df: pl.DataFrame, column: str) -> np.ndarray:
    if column not in df.columns:
        return np.array([])
    return df.select(pl.col(column).drop_nulls()).to_series().to_numpy()


def _quantile(values: np.ndarray, q: float) -> float:
    return float(np.quantile(values, q)) if len(values) else 0.0


def _kde_mode(values: np.ndarray) -> float:
    reshaped = values.reshape(-1, 1)
    bandwidth = max(float(np.std(values)), 1e-6)
    kde = KernelDensity(kernel="gaussian", bandwidth=bandwidth).fit(reshaped)
    grid = np.linspace(values.min(), values.max(), 200).reshape(-1, 1)
    return float(grid[np.argmax(kde.score_samples(grid))][0])


def _spike_zscore(values: np.ndarray) -> float:
    std = float(np.std(values))
    if std == 0.0:
        return 0.0
    return float((np.max(values) - np.mean(values)) / std)


def _backtest(
    wallet: pl.DataFrame,
    ofi: np.ndarray,
    spread: np.ndarray,
    momentum: np.ndarray,
    depth: np.ndarray,
) -> dict:
    if wallet.is_empty():
        return _empty_backtest()
    tested = wallet
    rules = [
        pl.col("ofi_filled") > _quantile(ofi, 0.90),
        pl.col("spread_filled") <= _quantile(spread, 0.50),
        pl.col("price_momentum") >= _quantile(momentum, 0.50),
        pl.col("depth_imbalance_filled") >= _quantile(depth, 0.50),
    ]
    predicted = tested.with_columns(
        (rules[0] & rules[1] & rules[2] & rules[3]).alias("strategy_hit")
    )
    hits = predicted.filter(pl.col("strategy_hit"))
    buy_hits = hits.filter(pl.col("side").str.to_lowercase() == "buy").height
    buy_total = tested.filter(pl.col("side").str.to_lowercase() == "buy").height
    recall = hits.height / tested.height if tested.height else 0.0
    precision = buy_hits / hits.height if hits.height else 0.0
    buy_recall = buy_hits / buy_total if buy_total else 0.0
    return {
        "samples": tested.height,
        "hits": hits.height,
        "coverage": recall,
        "precision_proxy": precision,
        "recall_proxy": recall,
        "buy_recall_proxy": buy_recall,
        "reproducibility_score": min((recall * 2.0 + precision) / 3.0, 1.0),
    }


def _empty_backtest() -> dict:
    return {
        "samples": 0,
        "hits": 0,
        "coverage": 0.0,
        "precision_proxy": 0.0,
        "recall_proxy": 0.0,
        "buy_recall_proxy": 0.0,
        "reproducibility_score": 0.0,
    }


def _research_note(
    wallet: pl.DataFrame,
    backtest: dict,
    ofi: np.ndarray,
    spread: np.ndarray,
    depth: np.ndarray,
) -> str:
    distinct_markets = wallet.get_column("market_id").n_unique()
    if distinct_markets <= 3 and _spike_zscore(ofi) > 2.0:
        archetype = "information-edge candidate"
    elif wallet.height >= 1000 and _quantile(spread, 0.50) <= 0.02:
        archetype = "market-making or stat-arb candidate"
    elif _spike_zscore(depth) > 2.0:
        archetype = "liquidity-imbalance timing candidate"
    else:
        archetype = "mixed alpha candidate"
    return (
        f"{archetype}; rule coverage={backtest['coverage']:.2%}, "
        f"precision_proxy={backtest['precision_proxy']:.2%}, "
        f"ofi_spike_z={_spike_zscore(ofi):.2f}, spread_p50={_quantile(spread, 0.50):.4f}"
    )


def _explainability_score(
    ofi: np.ndarray,
    spread: np.ndarray,
    momentum: np.ndarray,
    depth: np.ndarray,
    backtest: dict,
) -> float:
    if len(ofi) == 0:
        return 0.0
    ofi_score = min(abs(_spike_zscore(ofi)) / 5.0, 1.0)
    spread_score = 0.0 if len(spread) == 0 else min(abs(_spike_zscore(spread)) / 5.0, 1.0)
    momentum_score = 0.0 if len(momentum) == 0 else min(abs(_spike_zscore(momentum)) / 5.0, 1.0)
    depth_score = 0.0 if len(depth) == 0 else min(abs(_spike_zscore(depth)) / 5.0, 1.0)
    reproducibility = float(backtest.get("reproducibility_score", 0.0))
    return float((ofi_score + spread_score + momentum_score + depth_score + reproducibility) / 5.0)
