import polars as pl


def add_timing_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "published_at" in out.columns:
        out = out.with_columns(_pre_news_lag_expr())
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


def _pre_news_lag_expr() -> pl.Expr:
    return (
        pl.col("timestamp").dt.timestamp("ms") - pl.col("published_at").dt.timestamp("ms")
    ).truediv(1000).alias("pre_news_lag_secs")
