import polars as pl

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
]


def infer_wallet_rules(joined: pl.DataFrame, min_samples: int) -> dict:
    wallets = []
    for account in joined.get_column("account").unique().to_list():
        wallet = joined.filter(pl.col("account") == account)
        if wallet.height < min_samples:
            wallets.append(_small_sample(account, wallet.height))
            continue
        wallets.append(_wallet_rule(account, wallet))
    return {"version": 1, "rows": joined.height, "wallets": wallets}


def _wallet_rule(account: str, wallet: pl.DataFrame) -> dict:
    mining = mine_wallet(wallet)
    researcher = research_note(wallet, mining)
    buy = wallet.filter(pl.col("side").str.to_lowercase() == "buy")
    sell = wallet.filter(pl.col("side").str.to_lowercase() == "sell")
    return {
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
