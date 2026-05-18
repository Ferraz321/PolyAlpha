from dataclasses import dataclass
from pathlib import Path

from .weather_sources import fetch_open_meteo_archive, fetch_open_meteo_forecast_history


@dataclass
class WeatherContextRun:
    name: str
    rows: int


def fetch_weather_context(profile_dir: Path, locations_csv: Path, rules: dict) -> list[WeatherContextRun]:
    if not has_weather_category(rules):
        return []
    runs = []
    observations = profile_dir / "weather_observations.csv"
    if not observations.exists():
        rows = fetch_open_meteo_archive(
            profile_dir=profile_dir,
            locations_csv=locations_csv,
            out=observations,
        )
        runs.append(WeatherContextRun("fetch-weather-open-meteo", rows))
    forecasts = profile_dir / "forecast_history.csv"
    if not forecasts.exists():
        rows = fetch_open_meteo_forecast_history(
            profile_dir=profile_dir,
            locations_csv=locations_csv,
            out=forecasts,
        )
        runs.append(WeatherContextRun("fetch-weather-forecast-history", rows))
    return runs


def has_weather_category(rules: dict) -> bool:
    for wallet in rules.get("wallets", []):
        categories = wallet.get("market_categories", [])
        if any(category.get("id") == "weather_temperature" for category in categories):
            return True
    return False
