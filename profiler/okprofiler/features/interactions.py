import polars as pl


def add_interaction_factors(df: pl.DataFrame) -> pl.DataFrame:
    expressions = []
    columns = set(df.columns)
    if {"entry_hour_utc", "prior_repeat_hour_motif_score"}.issubset(columns):
        expressions.append(
            (
                pl.col("entry_hour_utc").cast(pl.Float64).fill_null(0.0)
                * pl.col("prior_repeat_hour_motif_score").cast(pl.Float64).fill_null(0.0)
            ).alias("hour_motif_timing_edge")
        )
    if {"temperature_mid_f", "prior_repeat_hour_motif_score"}.issubset(columns):
        expressions.append(
            (
                pl.col("temperature_mid_f").cast(pl.Float64).fill_null(0.0)
                * pl.col("prior_repeat_hour_motif_score").cast(pl.Float64).fill_null(0.0)
            ).alias("temperature_motif_edge")
        )
    if {"prior_same_market_trade_count", "prior_repeat_hour_motif_score"}.issubset(columns):
        expressions.append(
            (
                pl.col("prior_same_market_trade_count").cast(pl.Float64).fill_null(0.0)
                * pl.col("prior_repeat_hour_motif_score").cast(pl.Float64).fill_null(0.0)
            ).alias("prior_reentry_hour_motif_edge")
        )
    if {"prior_same_market_trade_count", "prior_buy_ratio"}.issubset(columns):
        expressions.append(
            (
                pl.col("prior_same_market_trade_count").cast(pl.Float64).fill_null(0.0)
                * pl.col("prior_buy_ratio").cast(pl.Float64).fill_null(0.0)
            ).alias("prior_reentry_buy_bias_edge")
        )
    return df.with_columns(expressions) if expressions else df
