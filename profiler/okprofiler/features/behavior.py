import polars as pl


def add_behavior_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not {"account", "market_id", "side"}.issubset(set(df.columns)):
        return df
    buy = pl.col("side").str.to_lowercase() == "buy"
    out = df.with_columns(
        [
            pl.len().over(["account", "market_id"]).alias("same_market_reentry_count"),
            buy.cast(pl.Float64).mean().over("account").alias("buy_ratio"),
        ]
    )
    if "timestamp" not in out.columns:
        return out
    sorted_out = out.with_row_index("__row_nr").sort(["account", "timestamp", "market_id", "side"])
    prior_account = (pl.col("account").cum_count().over("account").cast(pl.Int64) - 1).clip(0, None)
    prior_same_market = (
        pl.col("market_id").cum_count().over(["account", "market_id"]).cast(pl.Int64) - 1
    ).clip(0, None)
    expressions = [
        prior_account.alias("_prior_account_trade_count"),
        prior_same_market.alias("prior_same_market_trade_count"),
        pl.when(prior_account > 0)
        .then(prior_same_market.cast(pl.Float64) / prior_account.cast(pl.Float64))
        .otherwise(0.0)
        .alias("prior_market_reentry_rate"),
    ]
    if "entry_hour_utc" in sorted_out.columns:
        prior_hour = (
            pl.col("entry_hour_utc").cum_count().over(["account", "entry_hour_utc"]).cast(pl.Int64) - 1
        ).clip(0, None)
        prior_entry_motif = (
            pl.col("side")
            .cum_count()
            .over(["account", "market_id", "side", "entry_hour_utc"])
            .cast(pl.Int64)
            - 1
        ).clip(0, None)
        expressions.extend(
            [
                prior_entry_motif.alias("prior_repeat_entry_motif_count"),
                pl.when(prior_account > 0)
                .then(prior_hour.cast(pl.Float64) / prior_account.cast(pl.Float64))
                .otherwise(0.0)
                .alias("prior_repeat_hour_motif_score"),
            ]
        )
    buy_flag = buy.cast(pl.Int64)
    sorted_out = sorted_out.with_columns(expressions)
    sorted_out = sorted_out.with_columns(
        pl.when(pl.col("_prior_account_trade_count") > 0)
        .then(
            (buy_flag.cum_sum().over("account") - buy_flag).cast(pl.Float64)
            / pl.col("_prior_account_trade_count").cast(pl.Float64)
        )
        .otherwise(0.0)
        .alias("prior_buy_ratio")
    )
    return sorted_out.sort("__row_nr").drop(["__row_nr", "_prior_account_trade_count"])
