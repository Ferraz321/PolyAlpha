import polars as pl


def add_reverse_engineering_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = _add_forward_move_factors(df)
    out = _add_exit_quality_factors(out)
    out = _add_sector_factors(out)
    out = _add_lead_time_factors(out)
    out = _add_repeated_motif_factors(out)
    out = _add_cross_category_edge_factors(out)
    return out


def _add_forward_move_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"market_id", "timestamp", "price", "side"}
    if not required.issubset(set(df.columns)):
        return df
    out = df.sort(["market_id", "timestamp"]).with_columns(
        [
            pl.col("price").cast(pl.Float64).shift(-1).over("market_id").alias("_next_market_price"),
            pl.col("timestamp").shift(-1).over("market_id").alias("_next_market_timestamp"),
        ]
    )
    next_lag_secs = (
        pl.col("_next_market_timestamp").dt.timestamp("ms") - pl.col("timestamp").dt.timestamp("ms")
    ).truediv(1000)
    raw_move = pl.col("_next_market_price") - pl.col("price").cast(pl.Float64)
    signed_move = (
        pl.when(pl.col("side").str.to_lowercase() == "buy")
        .then(raw_move)
        .when(pl.col("side").str.to_lowercase() == "sell")
        .then(-raw_move)
        .otherwise(raw_move)
    )
    out = out.with_columns(
        [
            raw_move.fill_null(0.0).alias("forward_price_move"),
            signed_move.fill_null(0.0).alias("entry_forward_edge"),
            pl.when(signed_move > 0.0)
            .then(next_lag_secs)
            .otherwise(None)
            .alias("entry_before_move_secs"),
            pl.when(next_lag_secs > 0.0)
            .then(signed_move.fill_null(0.0) / (1.0 + next_lag_secs.truediv(3600)))
            .otherwise(0.0)
            .alias("lead_time_evidence"),
        ]
    )
    return out.drop(["_next_market_price", "_next_market_timestamp"])


def _add_exit_quality_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"account", "market_id", "price", "side"}
    if not required.issubset(set(df.columns)):
        return df
    buy_price = (
        pl.when(pl.col("side").str.to_lowercase() == "buy")
        .then(pl.col("price").cast(pl.Float64))
        .otherwise(None)
    )
    market_mean = pl.col("price").cast(pl.Float64).mean().over("market_id")
    out = df.with_columns(
        [
            buy_price.mean().over(["account", "market_id"]).alias("_wallet_market_buy_price"),
            market_mean.alias("_market_mean_price"),
        ]
    )
    return out.with_columns(
        [
            pl.when(pl.col("side").str.to_lowercase() == "sell")
            .then(pl.col("price").cast(pl.Float64) - pl.col("_wallet_market_buy_price"))
            .otherwise(None)
            .alias("exit_quality_proxy"),
            pl.when(pl.col("side").str.to_lowercase() == "buy")
            .then(pl.col("_market_mean_price") - pl.col("price").cast(pl.Float64))
            .otherwise(None)
            .alias("entry_price_advantage"),
        ]
    ).drop(["_wallet_market_buy_price", "_market_mean_price"])


def _add_sector_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"account", "sector"}
    if not required.issubset(set(df.columns)):
        return df
    out = df.with_columns(
        [
            pl.when(pl.col("sector").is_not_null())
            .then(pl.len().over(["account", "sector"]) / pl.len().over("account"))
            .otherwise(0.0)
            .alias("sector_concentration"),
            pl.when(pl.col("sector").is_not_null())
            .then(pl.len().over(["account", "sector"]))
            .otherwise(0)
            .alias("sector_trade_count"),
        ]
    )
    if {"price", "shares", "side"}.issubset(set(out.columns)):
        notional = pl.col("price").cast(pl.Float64) * pl.col("shares").cast(pl.Float64)
        signed_notional = (
            pl.when(pl.col("side").str.to_lowercase() == "sell")
            .then(notional)
            .when(pl.col("side").str.to_lowercase() == "buy")
            .then(-notional)
            .otherwise(0.0)
        )
        out = out.with_columns(
            signed_notional.sum().over(["account", "sector"]).alias("sector_pnl_proxy")
        )
    return out


def _add_cross_category_edge_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    columns = set(out.columns)
    if "entry_forward_edge" not in columns:
        return out
    positive_edge = pl.max_horizontal(
        pl.col("entry_forward_edge").cast(pl.Float64).fill_null(0.0),
        pl.lit(0.0),
    )
    expressions = []
    if {"account", "sector"}.issubset(columns):
        expressions.extend(
            [
                pl.col("entry_forward_edge")
                .cast(pl.Float64)
                .mean()
                .over(["account", "sector"])
                .alias("sector_entry_edge"),
                (
                    pl.col("sector_concentration").cast(pl.Float64).fill_null(0.0)
                    * positive_edge
                ).alias("sector_repeat_edge_score")
                if "sector_concentration" in columns
                else pl.lit(None).cast(pl.Float64).alias("sector_repeat_edge_score"),
                (
                    1.0
                    - pl.col("sector_concentration").cast(pl.Float64).fill_null(0.0)
                )
                .clip(0.0, 1.0)
                .alias("cross_sector_breadth")
                if "sector_concentration" in columns
                else pl.lit(None).cast(pl.Float64).alias("cross_sector_breadth"),
            ]
        )
    if "news_reaction_window" in columns:
        expressions.append(
            (
                pl.col("news_reaction_window").cast(pl.Float64).fill_null(0.0)
                * positive_edge
            ).alias("news_lead_entry_edge")
        )
    if "news_recency_hours" in columns:
        expressions.append(
            (
                positive_edge
                / (1.0 + pl.col("news_recency_hours").cast(pl.Float64).clip(0.0, None).fill_null(999.0))
            ).alias("news_recency_decay_edge")
        )
    if "is_last_24h" in columns:
        expressions.append(
            (
                pl.col("is_last_24h").cast(pl.Float64).fill_null(0.0)
                * positive_edge
            ).alias("settlement_window_edge")
        )
    if {"is_last_24h", "resolution_lead_time_hours"}.issubset(columns):
        expressions.append(
            (
                pl.col("is_last_24h").cast(pl.Float64).fill_null(0.0)
                * positive_edge
                / (1.0 + pl.col("resolution_lead_time_hours").cast(pl.Float64).clip(0.0, None).fill_null(999.0))
            ).alias("settlement_urgency_edge")
        )
    microstructure_columns = {
        "ofi_filled",
        "depth_imbalance_filled",
        "price_momentum",
        "spread_filled",
    }
    if microstructure_columns.intersection(columns):
        signal = pl.lit(0.0)
        if "ofi_filled" in columns:
            signal = signal + pl.col("ofi_filled").cast(pl.Float64).fill_null(0.0)
        if "depth_imbalance_filled" in columns:
            signal = signal + pl.col("depth_imbalance_filled").cast(pl.Float64).fill_null(0.0)
        if "price_momentum" in columns:
            signal = signal + pl.col("price_momentum").cast(pl.Float64).fill_null(0.0)
        if "spread_filled" in columns:
            signal = signal - pl.col("spread_filled").cast(pl.Float64).fill_null(0.0)
        expressions.append((positive_edge * signal).alias("microstructure_entry_edge"))
        pressure = pl.max_horizontal(signal, pl.lit(0.0))
        expressions.extend(
            [
                pressure.alias("microstructure_pressure_score"),
                (positive_edge * pressure).alias("microstructure_pressure_edge"),
            ]
        )
    if {"repeat_hour_motif_score", "repeat_entry_motif_count"}.issubset(columns):
        expressions.append(
            (
                pl.col("repeat_hour_motif_score").cast(pl.Float64).fill_null(0.0)
                * pl.col("repeat_entry_motif_count").cast(pl.Float64).fill_null(0.0)
                * positive_edge
            ).alias("event_motif_recurrence")
        )
    if {"sector_concentration", "repeat_hour_motif_score"}.issubset(columns):
        expressions.append(
            (
                pl.col("sector_concentration").cast(pl.Float64).fill_null(0.0)
                * pl.col("repeat_hour_motif_score").cast(pl.Float64).fill_null(0.0)
                * positive_edge
            ).alias("sector_motif_consistency_edge")
        )
    return out.with_columns(expressions) if expressions else out


def _add_lead_time_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "time_to_resolution_secs" in out.columns:
        out = out.with_columns(
            pl.col("time_to_resolution_secs").cast(pl.Float64).truediv(3600).alias("resolution_lead_time_hours")
        )
    if "pre_news_lag_secs" in out.columns:
        out = out.with_columns(
            [
                pl.col("pre_news_lag_secs").cast(pl.Float64).truediv(3600).alias("news_recency_hours"),
                pl.when(
                    (pl.col("pre_news_lag_secs").cast(pl.Float64) >= 0.0)
                    & (pl.col("pre_news_lag_secs").cast(pl.Float64) <= 6 * 3600)
                )
                .then(1.0)
                .otherwise(0.0)
                .alias("news_reaction_window"),
            ]
        )
    return out


def _add_repeated_motif_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"account", "market_id", "side"}
    if not required.issubset(set(df.columns)):
        return df
    out = df
    if "entry_hour_utc" in out.columns:
        out = out.with_columns(
            [
                pl.len().over(["account", "entry_hour_utc"]).truediv(pl.len().over("account")).alias(
                    "repeat_hour_motif_score"
                ),
                pl.len().over(["account", "market_id", "side", "entry_hour_utc"]).alias(
                    "repeat_entry_motif_count"
                ),
            ]
        )
    if "same_market_reentry_count" in out.columns:
        out = out.with_columns(
            pl.col("same_market_reentry_count")
            .cast(pl.Float64)
            .truediv(pl.len().over("account"))
            .alias("repeat_market_add_rate")
        )
    return out
