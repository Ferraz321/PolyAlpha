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
    out = df.sort(["weather_city", "timestamp"]).with_columns(
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
    out = _add_multi_model_factors(out)
    out = _add_city_bias_factors(out)
    return _add_bucket_normal_factors(out)


def _add_multi_model_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = df
    if "forecast_model_range_f" in out.columns:
        out = out.with_columns(pl.col("forecast_model_range_f").fill_null(0.0).alias("model_disagreement"))
    elif "forecast_model_std_f" in out.columns:
        out = out.with_columns((pl.col("forecast_model_std_f").fill_null(0.0) * 2.0).alias("model_disagreement"))
    elif "model_disagreement" not in out.columns:
        out = out.with_columns(pl.lit(None).cast(pl.Float64).alias("model_disagreement"))
    if "forecast_model_count" in out.columns:
        out = out.with_columns(pl.col("forecast_model_count").fill_null(1).cast(pl.Float64))
    return out


def _add_city_bias_factors(df: pl.DataFrame) -> pl.DataFrame:
    actual_column = _actual_temperature_column(df)
    if actual_column is None or "weather_city" not in df.columns:
        return df
    bias = pl.col(actual_column).cast(pl.Float64) - pl.col("forecast_temp_f").cast(pl.Float64)
    return df.with_columns(
        [
            bias.alias("forecast_bias_error_f"),
            bias.mean().over("weather_city").alias("city_forecast_bias_f"),
            bias.mean().over("weather_city").abs().alias("city_temperature_bias_edge"),
        ]
    )


def _add_bucket_normal_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not {"weather_city", "temperature_mid_f", "forecast_temp_f"}.issubset(set(df.columns)):
        return df
    city_normal = pl.col("forecast_temp_f").cast(pl.Float64).median().over("weather_city")
    return df.with_columns(
        [
            city_normal.alias("city_forecast_normal_f"),
            (pl.col("temperature_mid_f").cast(pl.Float64) - city_normal)
            .abs()
            .alias("bucket_distance_from_normal"),
        ]
    )


def _actual_temperature_column(df: pl.DataFrame) -> str | None:
    if "official_high_temp_f" in df.columns:
        return "official_high_temp_f"
    if "actual_high_temp_f" in df.columns:
        return "actual_high_temp_f"
    return None
