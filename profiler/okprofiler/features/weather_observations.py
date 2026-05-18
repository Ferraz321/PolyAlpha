import polars as pl


def add_weather_observation_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"actual_high_temp_f", "temperature_low_f", "temperature_high_f"}
    if not required.issubset(set(df.columns)):
        return df
    low = pl.col("temperature_low_f")
    high = pl.col("temperature_high_f")
    actual = pl.col("actual_high_temp_f")
    missing = actual.is_null() | (low.is_null() & high.is_null())
    distance = (
        pl.when(missing)
        .then(None)
        .when(low.is_null())
        .then(pl.max_horizontal(actual - high, pl.lit(0.0)))
        .when(high.is_null())
        .then(pl.max_horizontal(low - actual, pl.lit(0.0)))
        .when(actual < low)
        .then(low - actual)
        .when(actual > high)
        .then(actual - high)
        .otherwise(0.0)
    )
    inside = (
        pl.when(missing)
        .then(None)
        .when(low.is_null())
        .then((actual <= high).cast(pl.Float64))
        .when(high.is_null())
        .then((actual >= low).cast(pl.Float64))
        .otherwise(((actual >= low) & (actual <= high)).cast(pl.Float64))
    )
    return df.with_columns(
        [
            distance.alias("actual_temp_distance_to_bucket"),
            inside.alias("actual_temp_inside_bucket"),
            pl.when(low.is_not_null() & high.is_not_null())
            .then(actual - ((low + high) / 2.0))
            .otherwise(None)
            .alias("actual_temp_error_to_mid_f"),
        ]
    )
