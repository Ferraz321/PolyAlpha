import re

import polars as pl


WEATHER_RE = re.compile(
    r"highest-temperature-in-(?P<city>[a-z-]+)-on-(?P<month>[a-z]+)-(?P<day>\d{1,2})-(?P<year>\d{4})"
)
RANGE_RE = re.compile(r"(?<![a-z0-9])(?P<low>\d{1,3})-(?P<high>\d{1,3})\s*°?\s*f")
TITLE_CITY_RE = re.compile(r"temperature in (?P<city>[a-zA-Z -]+?) be")


def add_weather_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not any(column in df.columns for column in ["event_slug", "market_slug", "title"]):
        return df
    rows = [_parse_row(row) for row in df.iter_rows(named=True)]
    parsed = pl.DataFrame(rows) if rows else _empty_weather(df.height)
    parsed = parsed.with_columns(pl.Series("__row_nr", range(parsed.height)))
    base = df.with_row_index("__row_nr")
    out = base.join(parsed, on="__row_nr", how="left").drop("__row_nr")
    return _add_account_weather_factors(out)


def _parse_row(row: dict) -> dict:
    text = " ".join(
        str(row.get(column) or "")
        for column in ["event_slug", "market_slug", "title", "outcome"]
    ).lower()
    slug = str(row.get("event_slug") or row.get("market_slug") or "").lower()
    weather = WEATHER_RE.search(slug)
    temp_range = RANGE_RE.search(text)
    low = int(temp_range.group("low")) if temp_range else None
    high = int(temp_range.group("high")) if temp_range else None
    title_city = TITLE_CITY_RE.search(text)
    city = weather.group("city").replace("-", " ") if weather else None
    city = city or (title_city.group("city").strip() if title_city else None)
    is_weather = weather is not None or "temperature" in text or "weather" in text
    return {
        "is_weather_market": 1.0 if is_weather else 0.0,
        "weather_city": city,
        "temperature_low_f": low,
        "temperature_high_f": high,
        "temperature_mid_f": None if low is None or high is None else (low + high) / 2.0,
        "temperature_bucket_width_f": None if low is None or high is None else high - low,
    }


def _empty_weather(height: int) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "is_weather_market": [0.0] * height,
            "weather_city": [None] * height,
            "temperature_low_f": [None] * height,
            "temperature_high_f": [None] * height,
            "temperature_mid_f": [None] * height,
            "temperature_bucket_width_f": [None] * height,
        }
    )


def _add_account_weather_factors(df: pl.DataFrame) -> pl.DataFrame:
    if "account" not in df.columns:
        return df
    return df.with_columns(
        [
            pl.col("is_weather_market").mean().over("account").alias("weather_market_ratio"),
            pl.when(pl.col("weather_city").is_not_null())
            .then(pl.len().over(["account", "weather_city"]) / pl.len().over("account"))
            .otherwise(0.0)
            .alias("weather_city_concentration"),
        ]
    )
