import polars as pl


def add_timing_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "published_at" in out.columns:
        out = out.with_columns(_pre_news_lag_expr())
    if "timestamp" in out.columns:
        hour = pl.col("timestamp").dt.hour().cast(pl.Int64)
        minute = pl.col("timestamp").dt.minute().cast(pl.Int64)
        second = pl.col("timestamp").dt.second().cast(pl.Int64)
        node_hour = (hour // 6) * 6
        seconds_since_midnight = (
            hour * 3600 + minute * 60 + second
        )
        out = out.with_columns(
            [
                hour.alias("entry_hour_utc"),
                (seconds_since_midnight - node_hour * 3600).cast(pl.Float64).alias("nwp_node_lag_secs"),
                ((hour >= 18) & (hour <= 22)).cast(pl.Float64).alias("late_day_temperature_nowcast_edge"),
            ]
        )
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
