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
        strategies.append(
            {
                "id": f"reverse_{wallet['account'][:10]}",
                "source_wallet": wallet["account"],
                "enabled": False,
                "trigger": {
                    "all": [
                        {"feature": "ofi", "op": ">", "value": ofi_threshold},
                        {"feature": "spread", "op": "<=", "value": spread_threshold},
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
    lag = _numeric(wallet, "feature_lag_secs")
    buy = wallet.filter(pl.col("side").str.to_lowercase() == "buy")
    sell = wallet.filter(pl.col("side").str.to_lowercase() == "sell")
    return {
        "account": account,
        "samples": wallet.height,
        "buy_samples": buy.height,
        "sell_samples": sell.height,
        "ofi": _distribution(ofi),
        "spread": _distribution(spread),
        "feature_lag_secs": _distribution(lag),
        "candidate_rule": _candidate_rule(ofi, spread),
        "explainability_score": _explainability_score(ofi, spread),
    }


def _small_sample(account: str, samples: int) -> dict:
    return {
        "account": account,
        "samples": samples,
        "status": "small_sample",
        "candidate_rule": "collect more observations before inferring thresholds",
    }


def _candidate_rule(ofi: np.ndarray, spread: np.ndarray) -> str:
    ofi_p90 = _quantile(ofi, 0.90)
    spread_p50 = _quantile(spread, 0.50)
    return f"trigger when ofi > {ofi_p90:.6f} and spread <= {spread_p50:.6f}"


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


def _explainability_score(ofi: np.ndarray, spread: np.ndarray) -> float:
    if len(ofi) == 0:
        return 0.0
    ofi_score = min(abs(_spike_zscore(ofi)) / 5.0, 1.0)
    spread_score = 0.0 if len(spread) == 0 else min(abs(_spike_zscore(spread)) / 5.0, 1.0)
    return float((ofi_score + spread_score) / 2.0)
