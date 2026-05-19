from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .clustering import cluster_wallets, persist_clusters, write_clusters
from .diagnostics import build_diagnostics, write_diagnostics
from .factor_reporting import write_factor_outputs
from .features import add_derived_factors, extract_clob_features
from .report import write_reports
from .research_matrix import run_research_matrix
from .rules import infer_wallet_rules
from .strategy import strategy_config_from_rules
from .validation import (
    approved_live_features,
    persist_validations,
    validate_factor_table,
    write_validations,
)


@dataclass(frozen=True)
class ProfilerConfig:
    fills_path: Path
    clob_path: Path
    news_path: Path | None
    markets_path: Path | None
    weather_path: Path | None
    forecast_path: Path | None
    weather_events_path: Path | None
    official_weather_path: Path | None
    factor_out: Path | None
    strategy_out: Path | None
    report_out: Path | None
    html_out: Path | None
    diagnostics_out: Path | None
    factor_summary_out: Path | None
    factor_log_out: Path | None
    lookback_secs: int
    min_samples: int
    research_engines: list[str]
    validation_out: Path | None = None
    validation_db: Path | None = None
    clusters_out: Path | None = None
    clusters_db: Path | None = None


def run_profiler(config: ProfilerConfig) -> dict:
    fills = _read_fills(config.fills_path)
    if fills.is_empty():
        raise SystemExit("no fills to profile")
    clob = _read_optional_csv(config.clob_path, {"payload": pl.Utf8, "received_at": pl.Datetime})
    features = extract_clob_features(clob)
    joined = join_market_state(fills, features, config.lookback_secs)
    joined = attach_news(joined, config.news_path)
    joined = attach_market_metadata(joined, config.markets_path)
    factor_table = add_derived_factors(build_factor_table(joined))
    factor_table = attach_weather_observations(factor_table, config.weather_path)
    factor_table = attach_weather_forecasts(factor_table, config.forecast_path)
    factor_table = attach_weather_events(factor_table, config.weather_events_path)
    factor_table = attach_official_weather(factor_table, config.official_weather_path)
    factor_table = add_derived_factors(factor_table)
    if config.factor_out is not None:
        config.factor_out.parent.mkdir(parents=True, exist_ok=True)
        factor_table.write_parquet(config.factor_out)
    diagnostics = build_diagnostics(
        fills=fills,
        clob=clob,
        clob_features=features,
        factor_table=factor_table,
        news_path=config.news_path,
        markets_path=config.markets_path,
        weather_path=config.weather_path,
        forecast_path=config.forecast_path,
        weather_events_path=config.weather_events_path,
        official_weather_path=config.official_weather_path,
    )
    if config.diagnostics_out is not None:
        write_diagnostics(diagnostics, config.diagnostics_out)
    disabled_factors = _disabled_factors(diagnostics)
    rules = infer_wallet_rules(factor_table, config.min_samples, disabled_factors)
    rules["diagnostics"] = diagnostics
    rules["research_matrix"] = run_research_matrix(factor_table, config.research_engines)
    clusters = cluster_wallets(factor_table)
    rules["wallet_clusters"] = clusters
    if config.clusters_out is not None:
        write_clusters(clusters, config.clusters_out)
    if config.clusters_db is not None:
        rules["wallet_clusters_persisted"] = persist_clusters(config.clusters_db, clusters)
    validations = validate_factor_table(factor_table)
    rules["factor_validations"] = validations
    if config.validation_out is not None:
        write_validations(validations, config.validation_out)
    if config.validation_db is not None:
        rules["factor_validations_persisted"] = persist_validations(
            config.validation_db,
            validations,
        )
    if config.report_out is not None or config.html_out is not None:
        write_reports(rules, config.report_out, config.html_out)
    if config.strategy_out is not None:
        config.strategy_out.parent.mkdir(parents=True, exist_ok=True)
        config.strategy_out.write_text(
            strategy_config_from_rules(rules, approved_live_features(validations)),
            encoding="utf-8",
        )
    write_factor_outputs(rules, config.factor_summary_out, config.factor_log_out)
    return rules


def _disabled_factors(diagnostics: dict) -> set[str]:
    return {
        row["factor"]
        for row in diagnostics.get("factor_coverage", [])
        if not row.get("available", False)
    }


def join_market_state(
    fills: pl.DataFrame,
    features: pl.DataFrame,
    lookback_secs: int,
) -> pl.DataFrame:
    if features.is_empty():
        return fills.with_columns(
            pl.lit(None).cast(pl.Float64).alias("ofi"),
            pl.lit(None).cast(pl.Float64).alias("spread"),
            pl.lit(None).cast(pl.Float64).alias("best_bid"),
            pl.lit(None).cast(pl.Float64).alias("best_ask"),
            pl.lit(None).cast(pl.Float64).alias("mid_price"),
            pl.lit(None).cast(pl.Float64).alias("depth_imbalance"),
            pl.lit(None).cast(pl.Datetime).alias("received_at"),
        )
    return fills.sort("timestamp").join_asof(
        features.sort("received_at"),
        left_on="timestamp",
        right_on="received_at",
        by_left="market_id",
        by_right="asset_id",
        strategy="backward",
        tolerance=f"{lookback_secs}s",
        check_sortedness=False,
    )


def _read_optional_csv(path: Path, schema: dict) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame(schema=schema)
    return pl.read_csv(path, try_parse_dates=True)


def _read_fills(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        try_parse_dates=True,
        schema_overrides={
            "account": pl.Utf8,
            "market_id": pl.Utf8,
            "side": pl.Utf8,
        },
    )


def _read_markets(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        try_parse_dates=True,
        schema_overrides={
            "asset_id": pl.Utf8,
            "condition_id": pl.Utf8,
            "market_slug": pl.Utf8,
            "event_slug": pl.Utf8,
            "sector": pl.Utf8,
        },
    )


def attach_news(joined: pl.DataFrame, news_path: Path | None) -> pl.DataFrame:
    if news_path is None or not news_path.exists():
        return joined.with_columns(pl.lit(None).cast(pl.Utf8).alias("last_news_slug"))
    news = pl.read_csv(news_path, try_parse_dates=True).sort("published_at")
    return joined.sort("timestamp").join_asof(
        news,
        left_on="timestamp",
        right_on="published_at",
        strategy="backward",
    )


def attach_market_metadata(joined: pl.DataFrame, markets_path: Path | None) -> pl.DataFrame:
    if markets_path is None or not markets_path.exists():
        return joined.with_columns(pl.lit(None).cast(pl.Datetime).alias("resolution_time"))
    markets = _read_markets(markets_path)
    if "asset_id" not in markets.columns or "resolution_time" not in markets.columns:
        return joined.with_columns(pl.lit(None).cast(pl.Datetime).alias("resolution_time"))
    columns = [
        column
        for column in ["asset_id", "resolution_time", "sector", "event_slug", "market_slug"]
        if column in markets.columns
    ]
    return joined.join(
        markets.select(columns),
        left_on="market_id",
        right_on="asset_id",
        how="left",
    )


def attach_weather_observations(joined: pl.DataFrame, weather_path: Path | None) -> pl.DataFrame:
    required = {"weather_city", "weather_event_date"}
    if weather_path is None or not weather_path.exists() or not required.issubset(set(joined.columns)):
        return joined
    weather = pl.read_csv(
        weather_path,
        try_parse_dates=True,
        schema_overrides={"city": pl.Utf8, "event_date": pl.Utf8},
    )
    if not {"city", "event_date", "actual_high_temp_f"}.issubset(set(weather.columns)):
        return joined
    daily = weather.select(
        [
            pl.col("city").str.to_lowercase().alias("weather_city"),
            pl.col("event_date").alias("weather_event_date"),
            pl.col("actual_high_temp_f").cast(pl.Float64),
            pl.col("source").cast(pl.Utf8),
        ]
    ).unique(["weather_city", "weather_event_date"])
    return joined.join(daily, on=["weather_city", "weather_event_date"], how="left")


def attach_weather_forecasts(joined: pl.DataFrame, forecast_path: Path | None) -> pl.DataFrame:
    required = {"weather_city", "timestamp"}
    if forecast_path is None or not forecast_path.exists() or not required.issubset(set(joined.columns)):
        return joined
    forecasts = pl.read_csv(
        forecast_path,
        try_parse_dates=True,
        schema_overrides={"city": pl.Utf8},
    )
    if not {"city", "timestamp", "forecast_temp_f"}.issubset(set(forecasts.columns)):
        return joined
    hourly = forecasts.select(
        [
            pl.col("city").str.to_lowercase().alias("forecast_city"),
            pl.col("timestamp").dt.replace_time_zone("UTC").alias("forecast_timestamp"),
            pl.col("forecast_temp_f").cast(pl.Float64),
            pl.col("source").cast(pl.Utf8).alias("forecast_source"),
        ]
    ).sort(["forecast_city", "forecast_timestamp"])
    return joined.sort(["weather_city", "timestamp"]).join_asof(
        hourly,
        left_on="timestamp",
        right_on="forecast_timestamp",
        by_left="weather_city",
        by_right="forecast_city",
        strategy="backward",
        tolerance="6h",
        check_sortedness=False,
    )


def attach_weather_events(joined: pl.DataFrame, weather_events_path: Path | None) -> pl.DataFrame:
    required = {"market_slug", "event_slug"}
    if (
        weather_events_path is None
        or not weather_events_path.exists()
        or not required.issubset(set(joined.columns))
    ):
        return joined
    events = pl.read_csv(
        weather_events_path,
        schema_overrides={
            "event_slug": pl.Utf8,
            "market_slug": pl.Utf8,
            "official_station_id": pl.Utf8,
            "resolution_source": pl.Utf8,
        },
    )
    expected = {
        "event_slug",
        "market_slug",
        "official_station_id",
        "resolution_source",
        "ladder_yes_price",
        "ladder_bucket_count",
        "ladder_price_sum",
        "ladder_price_rank",
    }
    if not expected.issubset(set(events.columns)):
        return joined
    columns = [
        "event_slug",
        "market_slug",
        "official_station_id",
        "resolution_source",
        "ladder_yes_price",
        "ladder_best_bid",
        "ladder_best_ask",
        "ladder_last_trade_price",
        "ladder_market_closed",
        "ladder_bucket_count",
        "ladder_price_sum",
        "ladder_price_rank",
    ]
    return joined.join(events.select([column for column in columns if column in events.columns]), on=["event_slug", "market_slug"], how="left")


def attach_official_weather(joined: pl.DataFrame, official_weather_path: Path | None) -> pl.DataFrame:
    required = {"official_station_id", "weather_event_date"}
    if (
        official_weather_path is None
        or not official_weather_path.exists()
        or not required.issubset(set(joined.columns))
    ):
        return joined
    official = pl.read_csv(
        official_weather_path,
        try_parse_dates=True,
        schema_overrides={"official_station_id": pl.Utf8, "event_date": pl.Utf8},
    )
    expected = {"official_station_id", "event_date", "official_high_temp_f"}
    if not expected.issubset(set(official.columns)):
        return joined
    daily = official.select(
        [
            pl.col("official_station_id"),
            pl.col("event_date").alias("weather_event_date"),
            pl.col("official_high_temp_f").cast(pl.Float64),
        ]
    ).unique(["official_station_id", "weather_event_date"])
    return joined.join(daily, on=["official_station_id", "weather_event_date"], how="left")


def build_factor_table(joined: pl.DataFrame) -> pl.DataFrame:
    timestamp = pl.col("timestamp")
    received_at = pl.col("received_at")
    with_base = joined.sort(["market_id", "timestamp"]).with_columns(
        [
            (timestamp.dt.timestamp("ms") - received_at.dt.timestamp("ms"))
            .truediv(1000)
            .alias("feature_lag_secs"),
            (pl.col("price") - pl.col("best_bid")).alias("distance_to_bid"),
            (pl.col("best_ask") - pl.col("price")).alias("distance_to_ask"),
            pl.col("ofi").fill_null(0.0).alias("ofi_filled"),
            pl.col("spread").fill_null(0.0).alias("spread_filled"),
            pl.col("depth_imbalance").fill_null(0.0).alias("depth_imbalance_filled"),
        ]
    )
    return with_base.with_columns(
        [
            pl.col("mid_price")
            .diff()
            .over("market_id")
            .fill_null(0.0)
            .alias("price_momentum"),
            (
                pl.col("resolution_time").dt.timestamp("ms")
                - pl.col("timestamp").dt.timestamp("ms")
            )
            .truediv(1000)
            .alias("time_to_resolution_secs"),
        ]
    )
