import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import polars as pl


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_open_meteo_archive(profile_dir: Path, locations_csv: Path, out: Path) -> int:
    locations = _read_locations(locations_csv)
    factor_table = profile_dir / "factor_table.parquet"
    if not factor_table.exists():
        raise SystemExit(f"missing factor table: {factor_table}")
    df = pl.read_parquet(factor_table)
    if not {"weather_city", "timestamp"}.issubset(set(df.columns)):
        raise SystemExit("factor table does not contain weather_city/timestamp")
    rows = []
    for city, window in _city_windows(df).items():
        if city not in locations:
            rows.append({"city": city, "event_date": window["start"], "status": "missing_coordinates"})
            continue
        lat, lon = locations[city]
        rows.extend(_daily_highs(city, _fetch_city(city, lat, lon, window["start"], window["end"])))
    _write_rows(out, rows)
    return len(rows)


def _city_windows(df: pl.DataFrame) -> dict[str, dict[str, str]]:
    windows = (
        df.filter(pl.col("weather_city").is_not_null() & pl.col("weather_event_date").is_not_null())
        .group_by("weather_city")
        .agg([pl.col("weather_event_date").min().alias("start"), pl.col("weather_event_date").max().alias("end")])
    )
    out = {}
    for row in windows.iter_rows(named=True):
        start = str(row["start"])
        end = str(row["end"])
        out[str(row["weather_city"]).lower()] = {"start": start, "end": end}
    return out


def _fetch_city(city: str, lat: float, lon: float, start: str, end: str) -> list[dict]:
    query = urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "hourly": "temperature_2m",
            "temperature_unit": "fahrenheit",
            "timezone": "UTC",
        }
    )
    with urlopen(f"{OPEN_METEO_ARCHIVE_URL}?{query}", timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    return [
        {
            "city": city,
            "timestamp": timestamp,
            "temperature_f": temp,
            "source": "open-meteo-archive",
            "status": "ok",
        }
        for timestamp, temp in zip(times, temps)
    ]


def _daily_highs(city: str, rows: list[dict]) -> list[dict]:
    highs = {}
    for row in rows:
        if row.get("status") != "ok" or row.get("temperature_f") is None:
            continue
        event_date = str(row["timestamp"])[:10]
        highs[event_date] = max(float(row["temperature_f"]), highs.get(event_date, float("-inf")))
    return [
        {
            "city": city,
            "event_date": event_date,
            "actual_high_temp_f": high,
            "source": "open-meteo-archive",
            "status": "ok",
        }
        for event_date, high in sorted(highs.items())
    ]


def _read_locations(path: Path) -> dict[str, tuple[float, float]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            row["city"].strip().lower(): (float(row["latitude"]), float(row["longitude"]))
            for row in reader
            if row.get("city") and row.get("latitude") and row.get("longitude")
        }


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["city", "event_date", "actual_high_temp_f", "source", "status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})
