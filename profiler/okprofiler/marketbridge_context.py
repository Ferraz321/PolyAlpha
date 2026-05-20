from pathlib import Path

import polars as pl


def attach_marketbridge_context(joined: pl.DataFrame, context_path: Path | None) -> pl.DataFrame:
    if context_path is None or not context_path.exists() or "timestamp" not in joined.columns:
        return joined
    context = pl.read_csv(
        context_path,
        try_parse_dates=True,
        schema_overrides={"feature": pl.Utf8, "source": pl.Utf8},
    )
    expected = {"timestamp", "feature", "value"}
    if not expected.issubset(set(context.columns)):
        return joined
    wide = (
        context.select(
            [
                pl.col("timestamp").dt.replace_time_zone("UTC"),
                pl.col("feature").cast(pl.Utf8),
                pl.col("value").cast(pl.Float64),
            ]
        )
        .drop_nulls(["timestamp", "feature", "value"])
        .group_by(["timestamp", "feature"])
        .agg(pl.col("value").last())
        .pivot(index="timestamp", on="feature", values="value")
        .sort("timestamp")
    )
    if wide.is_empty():
        return joined
    return joined.sort("timestamp").join_asof(
        wide,
        on="timestamp",
        strategy="backward",
        tolerance="7d",
        check_sortedness=False,
    )
