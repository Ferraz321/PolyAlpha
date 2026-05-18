import polars as pl


def add_behavior_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not {"account", "market_id", "side"}.issubset(set(df.columns)):
        return df
    buy = pl.col("side").str.to_lowercase() == "buy"
    return df.with_columns(
        [
            pl.len().over(["account", "market_id"]).alias("same_market_reentry_count"),
            buy.cast(pl.Float64).mean().over("account").alias("buy_ratio"),
        ]
    )
