import polars as pl


def add_weather_forecast_factors(df: pl.DataFrame) -> pl.DataFrame:
    required = {"forecast_temp_f", "temperature_low_f", "temperature_high_f"}
    if not required.issubset(set(df.columns)):
        return df
    low = pl.col("temperature_low_f")
    high = pl.col("temperature_high_f")
    forecast = pl.col("forecast_temp_f")
    missing = forecast.is_null() | (low.is_null() & high.is_null())
    distance = (
        pl.when(missing)
        .then(None)
        .when(low.is_null())
        .then(pl.max_horizontal(forecast - high, pl.lit(0.0)))
        .when(high.is_null())
        .then(pl.max_horizontal(low - forecast, pl.lit(0.0)))
        .when(forecast < low)
        .then(low - forecast)
        .when(forecast > high)
        .then(forecast - high)
        .otherwise(0.0)
    )
    inside = (
        pl.when(missing)
        .then(None)
        .when(low.is_null())
        .then((forecast <= high).cast(pl.Float64))
        .when(high.is_null())
        .then((forecast >= low).cast(pl.Float64))
        .otherwise(((forecast >= low) & (forecast <= high)).cast(pl.Float64))
    )
    return df.sort(["weather_city", "timestamp"]).with_columns(
        [
            distance.alias("forecast_error_to_bucket"),
            inside.alias("forecast_inside_bucket"),
            pl.col("forecast_temp_f").diff().over("weather_city").alias("forecast_delta_1h"),
            (pl.col("forecast_temp_f") - pl.col("forecast_temp_f").shift(6).over("weather_city")).alias(
                "forecast_delta_6h"
            ),
            pl.col("forecast_temp_f").rolling_std(window_size=6).over("weather_city").alias("forecast_volatility"),
        ]
    )
