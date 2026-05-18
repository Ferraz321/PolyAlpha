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
    out = _add_timing_factors(out)
    out = _add_behavior_factors(out)
    out = add_weather_factors(out)
    return out


def _pre_news_lag_expr() -> pl.Expr:
    return (
        pl.col("timestamp").dt.timestamp("ms") - pl.col("published_at").dt.timestamp("ms")
    ).truediv(1000).alias("pre_news_lag_secs")


def _add_timing_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "timestamp" in out.columns:
        out = out.with_columns(pl.col("timestamp").dt.hour().alias("entry_hour_utc"))
    if "time_to_resolution_secs" in out.columns:
        out = out.with_columns(
            [
                (pl.col("time_to_resolution_secs") <= 86400).cast(pl.Float64).alias("is_last_24h"),
                (pl.col("time_to_resolution_secs") <= 21600).cast(pl.Float64).alias("is_last_6h"),
            ]
        )
    return out


def _add_behavior_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not {"account", "market_id", "side"}.issubset(set(df.columns)):
        return df
    buy = pl.col("side").str.to_lowercase() == "buy"
    return df.with_columns(
        [
            pl.len().over(["account", "market_id"]).alias("same_market_reentry_count"),
            buy.cast(pl.Float64).mean().over("account").alias("buy_ratio"),
        ]
    )
