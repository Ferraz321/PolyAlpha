import json
from pathlib import Path

import polars as pl

from .features import FACTOR_SPECS


def build_diagnostics(
    fills: pl.DataFrame,
    clob: pl.DataFrame,
    clob_features: pl.DataFrame,
    factor_table: pl.DataFrame,
    news_path: Path | None,
    markets_path: Path | None,
    weather_path: Path | None,
    forecast_path: Path | None = None,
) -> dict:
    sources = {
        "fills": _source_status(fills, ["account", "market_id", "timestamp", "side", "price", "shares"]),
        "clob": _source_status(clob, ["payload", "received_at"]),
        "clob_features": _source_status(clob_features, ["asset_id", "received_at", "spread", "ofi"]),
        "news": _file_status(news_path, ["published_at"]),
        "markets": _file_status(markets_path, ["asset_id", "resolution_time"]),
        "weather_observations": _file_status(weather_path, ["city", "event_date", "actual_high_temp_f"]),
        "weather_forecasts": _file_status(forecast_path, ["city", "timestamp", "forecast_temp_f"]),
    }
    factors = [_factor_status(spec, factor_table, sources) for spec in FACTOR_SPECS]
    return {
        "ready": sources["fills"]["ready"] and sources["clob_features"]["ready"],
        "sources": sources,
        "factor_coverage": factors,
        "missing_actions": _missing_actions(sources, factors),
    }


def write_diagnostics(diagnostics: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(diagnostics, indent=2), encoding="utf-8")


def _source_status(df: pl.DataFrame, required: list[str]) -> dict:
    missing = [column for column in required if column not in df.columns]
    return {
        "ready": not missing and df.height > 0,
        "rows": df.height,
        "missing_columns": missing,
    }


def _file_status(path: Path | None, required: list[str]) -> dict:
    if path is None or not path.exists():
        return {"ready": False, "rows": 0, "missing_columns": required, "path": None if path is None else str(path)}
    try:
        df = pl.read_csv(path, try_parse_dates=True, infer_schema_length=0)
        return _source_status(df, required) | {"path": str(path)}
    except Exception as exc:
        return {"ready": False, "rows": 0, "missing_columns": required, "error": str(exc), "path": str(path)}


def _factor_status(spec, factor_table: pl.DataFrame, sources: dict) -> dict:
    available = spec.column in factor_table.columns
    non_null = 0
    if available:
        non_null = factor_table.select(pl.col(spec.column).drop_nulls()).height
    missing_sources = [source for source in spec.requires if not sources.get(source, {}).get("ready", False)]
    return {
        "factor": spec.column,
        "label": spec.label,
        "available": available and non_null > 0 and not missing_sources,
        "non_null_rows": non_null,
        "requires": list(spec.requires),
        "missing_sources": missing_sources,
    }


def _missing_actions(sources: dict, factors: list[dict]) -> list[str]:
    actions = []
    if not sources["clob_features"]["ready"]:
        actions.append("run watch-clob for the target asset pool before profiling")
    if not sources["markets"]["ready"]:
        actions.append("run fetch-gamma-markets or provide markets.csv for resolution/sector factors")
    if not sources["news"]["ready"]:
        actions.append("provide news.csv if you want pre-news information-edge evidence")
    if not sources["weather_observations"]["ready"]:
        actions.append("run fetch-weather-open-meteo for weather actual-temperature factors")
    if not sources["weather_forecasts"]["ready"]:
        actions.append("run fetch-weather-forecast-history for weather forecast-error factors")
    if not any(row["available"] for row in factors):
        actions.append("factor table has no usable factors; collect richer CLOB/metadata inputs")
    return actions
