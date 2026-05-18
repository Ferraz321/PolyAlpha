from dataclasses import dataclass

import polars as pl


@dataclass(frozen=True)
class FactorSpec:
    column: str
    label: str
    direction: str
    quantile: float
    live_feature: str | None = None


FACTOR_SPECS = [
    FactorSpec("ofi_filled", "order-flow imbalance", "high", 0.90, "ofi"),
    FactorSpec("spread_filled", "tight spread", "low", 0.50, "spread"),
    FactorSpec("depth_imbalance_filled", "depth imbalance", "high", 0.50, "depth_imbalance"),
    FactorSpec("price_momentum", "short-horizon price momentum", "high", 0.50, "price_momentum"),
    FactorSpec("abs_price_momentum", "absolute price shock", "high", 0.90),
    FactorSpec("feature_lag_secs", "fresh CLOB alignment", "low", 0.50),
    FactorSpec("distance_to_bid", "entry near bid", "low", 0.50),
    FactorSpec("distance_to_ask", "entry near ask", "low", 0.50),
    FactorSpec("trade_notional", "ticket size", "high", 0.75),
    FactorSpec("time_to_resolution_secs", "time to resolution", "high", 0.50),
]


def add_derived_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "shares" in out.columns and "price" in out.columns:
        out = out.with_columns((pl.col("shares") * pl.col("price")).alias("trade_notional"))
    if "price_momentum" in out.columns:
        out = out.with_columns(pl.col("price_momentum").abs().alias("abs_price_momentum"))
    if "feature_lag_secs" in out.columns:
        out = out.with_columns(pl.col("feature_lag_secs").fill_null(999999.0))
    return out


def available_specs(df: pl.DataFrame) -> list[FactorSpec]:
    return [spec for spec in FACTOR_SPECS if spec.column in df.columns]
