import re
from datetime import datetime

import polars as pl

from .semantic import parse_market_semantics


WEATHER_RE = re.compile(
    r"highest-temperature-in-(?P<city>[a-z-]+)-on-(?P<month>[a-z]+)-(?P<day>\d{1,2})-(?P<year>\d{4})"
)
RANGE_RE = re.compile(r"(?<![a-z0-9])(?P<low>\d{1,3})-(?P<high>\d{1,3})\s*°?\s*f")
BETWEEN_TITLE_RE = re.compile(r"between\s+(?P<low>\d{1,3})-(?P<high>\d{1,3})\s*°?\s*f")
HIGHER_TITLE_RE = re.compile(r"(?P<low>\d{1,3})\s*°?\s*f\s+or\s+higher")
BELOW_TITLE_RE = re.compile(r"(?P<high>\d{1,3})\s*°?\s*f\s+or\s+below")
BETWEEN_SLUG_RE = re.compile(r"-(?P<low>\d{1,3})-(?P<high>\d{1,3})f$")
HIGHER_SLUG_RE = re.compile(r"-(?P<low>\d{1,3})forhigher$")
BELOW_SLUG_RE = re.compile(r"-(?P<high>\d{1,3})forbelow$")
TITLE_CITY_RE = re.compile(r"temperature in (?P<city>[a-zA-Z -]+?) be")
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def add_weather_factors(df: pl.DataFrame) -> pl.DataFrame:
    if not any(column in df.columns for column in ["event_slug", "market_slug", "title"]):
        return df
    rows = [_parse_row(row) for row in df.iter_rows(named=True)]
    parsed = pl.DataFrame(rows, infer_schema_length=None) if rows else _empty_weather(df.height)
    parsed = parsed.with_columns(pl.Series("__row_nr", range(parsed.height)))
    base = df.with_row_index("__row_nr")
    out = base.join(parsed, on="__row_nr", how="left").drop("__row_nr")
    return _add_account_weather_factors(out)


def _parse_row(row: dict) -> dict:
    text = " ".join(
        str(row.get(column) or "")
        for column in ["event_slug", "market_slug", "title", "outcome"]
    ).lower()
    title_text = " ".join(str(row.get(column) or "") for column in ["title", "outcome"]).lower()
    slug = str(row.get("event_slug") or row.get("market_slug") or "").lower()
    weather = WEATHER_RE.search(slug)
    title_city = TITLE_CITY_RE.search(text)
    city = weather.group("city").replace("-", " ") if weather else None
    city = city or (title_city.group("city").strip() if title_city else None)
    is_weather = weather is not None or "temperature" in text or "weather" in text
    low, high, bucket_type = _parse_temperature_bucket(title_text, slug) if is_weather else (None, None, None)
    llm = _llm_fill(row, is_weather, city, weather, low, high, bucket_type)
    is_weather = bool(llm.get("is_weather_market", is_weather))
    city = llm.get("weather_city", city)
    event_date = llm.get("weather_event_date") or _event_date(weather)
    low = _coerce_int(llm.get("temperature_low_f", low))
    high = _coerce_int(llm.get("temperature_high_f", high))
    bucket_type = llm.get("temperature_bucket_type", bucket_type)
    return {
        "is_weather_market": 1.0 if is_weather else 0.0,
        "weather_city": city,
        "weather_event_date": event_date,
        "temperature_low_f": low,
        "temperature_high_f": high,
        "temperature_bucket_type": bucket_type,
        "temperature_mid_f": None if low is None or high is None else (low + high) / 2.0,
        "temperature_bucket_width_f": None if low is None or high is None else high - low,
        "is_low_temp_bucket": _flag(_bucket_anchor(low, high) is not None and _bucket_anchor(low, high) <= 40),
        "is_high_temp_bucket": _flag(_bucket_anchor(low, high) is not None and _bucket_anchor(low, high) >= 75),
        "is_extreme_temperature_bucket": _flag(
            _bucket_anchor(low, high) is not None
            and (_bucket_anchor(low, high) <= 32 or _bucket_anchor(low, high) >= 90)
        ),
    }


def _empty_weather(height: int) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "is_weather_market": [0.0] * height,
            "weather_city": [None] * height,
            "weather_event_date": [None] * height,
            "temperature_low_f": [None] * height,
            "temperature_high_f": [None] * height,
            "temperature_bucket_type": [None] * height,
            "temperature_mid_f": [None] * height,
            "temperature_bucket_width_f": [None] * height,
            "is_low_temp_bucket": [None] * height,
            "is_high_temp_bucket": [None] * height,
            "is_extreme_temperature_bucket": [None] * height,
        }
    )


def _add_account_weather_factors(df: pl.DataFrame) -> pl.DataFrame:
    if "account" not in df.columns:
        return df
    out = df.with_columns(
        [
            pl.col("is_weather_market").mean().over("account").alias("weather_market_ratio"),
            pl.when(pl.col("weather_city").is_not_null())
            .then(pl.len().over(["account", "weather_city"]) / pl.len().over("account"))
            .otherwise(0.0)
            .alias("weather_city_concentration"),
        ]
    )
    if "market_id" not in out.columns:
        return out
    breadth = (
        out.filter(pl.col("is_weather_market") == 1.0)
        .group_by("account")
        .agg(
            [
                pl.col("market_id").n_unique().alias("weather_market_breadth"),
                pl.col("weather_city").drop_nulls().n_unique().alias("weather_city_count"),
            ]
        )
    )
    if breadth.is_empty():
        return out.with_columns(
            [
                pl.lit(0).alias("weather_market_breadth"),
                pl.lit(0).alias("weather_city_count"),
            ]
        )
    return out.join(breadth, on="account", how="left").with_columns(
        [
            pl.col("weather_market_breadth").fill_null(0),
            pl.col("weather_city_count").fill_null(0),
        ]
    )


def _flag(value: bool) -> float | None:
    return 1.0 if value else 0.0


def _event_date(match) -> str | None:
    if match is None:
        return None
    month = MONTHS.get(match.group("month"))
    if month is None:
        return None
    try:
        return datetime(int(match.group("year")), month, int(match.group("day"))).date().isoformat()
    except ValueError:
        return None


def _parse_temperature_bucket(text: str, slug: str) -> tuple[int | None, int | None, str | None]:
    for pattern, source, kind in [
        (BETWEEN_TITLE_RE, text, "between"),
        (BETWEEN_SLUG_RE, slug, "between"),
        (HIGHER_TITLE_RE, text, "higher"),
        (HIGHER_SLUG_RE, slug, "higher"),
        (BELOW_TITLE_RE, text, "below"),
        (BELOW_SLUG_RE, slug, "below"),
    ]:
        match = pattern.search(source)
        if match:
            low = int(match.group("low")) if "low" in match.groupdict() and match.group("low") else None
            high = int(match.group("high")) if "high" in match.groupdict() and match.group("high") else None
            return low, high, kind
    match = RANGE_RE.search(text)
    if match:
        return int(match.group("low")), int(match.group("high")), "between"
    return None, None, None


def _bucket_anchor(low: int | None, high: int | None) -> float | None:
    if low is not None and high is not None:
        return (low + high) / 2.0
    if low is not None:
        return float(low)
    if high is not None:
        return float(high)
    return None


def _llm_fill(
    row: dict,
    is_weather: bool,
    city: str | None,
    weather_match,
    low: int | None,
    high: int | None,
    bucket_type: str | None,
) -> dict:
    if not is_weather and city and weather_match and (low is not None or high is not None) and bucket_type:
        return {}
    missing_core = not city or weather_match is None or (low is None and high is None) or not bucket_type
    return parse_market_semantics(row) if missing_core else {}


def _coerce_int(value) -> int | None:
    try:
        return None if value is None else int(float(value))
    except Exception:
        return None
