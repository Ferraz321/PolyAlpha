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
]


def available_specs(df: pl.DataFrame) -> list[FactorSpec]:
    return [spec for spec in FACTOR_SPECS if spec.column in df.columns]
