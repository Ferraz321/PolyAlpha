import polars as pl

from .weather import add_weather_factors


def add_derived_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "shares" in out.columns and "price" in out.columns:
        out = out.with_columns((pl.col("shares") * pl.col("price")).alias("trade_notional"))
    if "price_momentum" in out.columns:
        out = out.with_columns(pl.col("price_momentum").abs().alias("abs_price_momentum"))
    if "feature_lag_secs" in out.columns:
        out = out.with_columns(pl.col("feature_lag_secs").fill_null(999999.0))
    if "published_at" in out.columns:
        out = out.with_columns(_pre_news_lag_expr())
    out = add_weather_factors(out)
    return out


def _pre_news_lag_expr() -> pl.Expr:
    return (
        pl.col("timestamp").dt.timestamp("ms") - pl.col("published_at").dt.timestamp("ms")
    ).truediv(1000).alias("pre_news_lag_secs")
