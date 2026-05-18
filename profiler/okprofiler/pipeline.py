from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .features import extract_clob_features
from .report import write_reports
from .rules import infer_wallet_rules, strategy_config_from_rules


@dataclass(frozen=True)
class ProfilerConfig:
    fills_path: Path
    clob_path: Path
    news_path: Path | None
    markets_path: Path | None
    factor_out: Path | None
    strategy_out: Path | None
    report_out: Path | None
    html_out: Path | None
    lookback_secs: int
    min_samples: int


def run_profiler(config: ProfilerConfig) -> dict:
    fills = pl.read_csv(config.fills_path, try_parse_dates=True)
    if fills.is_empty():
        raise SystemExit("no fills to profile")
    clob = pl.read_csv(config.clob_path, try_parse_dates=True)
    features = extract_clob_features(clob)
    joined = join_market_state(fills, features, config.lookback_secs)
    joined = attach_news(joined, config.news_path)
    joined = attach_market_metadata(joined, config.markets_path)
    factor_table = build_factor_table(joined)
    if config.factor_out is not None:
        config.factor_out.parent.mkdir(parents=True, exist_ok=True)
        factor_table.write_parquet(config.factor_out)
    rules = infer_wallet_rules(factor_table, config.min_samples)
    if config.report_out is not None or config.html_out is not None:
        write_reports(rules, config.report_out, config.html_out)
    if config.strategy_out is not None:
        config.strategy_out.parent.mkdir(parents=True, exist_ok=True)
        config.strategy_out.write_text(
            strategy_config_from_rules(rules),
            encoding="utf-8",
        )
    return rules


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
    markets = pl.read_csv(markets_path, try_parse_dates=True)
    if "asset_id" not in markets.columns or "resolution_time" not in markets.columns:
        return joined.with_columns(pl.lit(None).cast(pl.Datetime).alias("resolution_time"))
    return joined.join(
        markets.select("asset_id", "resolution_time"),
        left_on="market_id",
        right_on="asset_id",
        how="left",
    )


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
