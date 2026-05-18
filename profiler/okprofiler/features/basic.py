import polars as pl


def add_basic_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "shares" in out.columns and "price" in out.columns:
        out = out.with_columns((pl.col("shares") * pl.col("price")).alias("trade_notional"))
    if "price_momentum" in out.columns:
        out = out.with_columns(pl.col("price_momentum").abs().alias("abs_price_momentum"))
    if "feature_lag_secs" in out.columns:
        out = out.with_columns(pl.col("feature_lag_secs").fill_null(999999.0))
    return out
