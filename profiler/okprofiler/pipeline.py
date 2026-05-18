from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .features import extract_clob_features
from .rules import infer_wallet_rules


@dataclass(frozen=True)
class ProfilerConfig:
    fills_path: Path
    clob_path: Path
    news_path: Path | None
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
    return infer_wallet_rules(joined, config.min_samples)


def join_market_state(
    fills: pl.DataFrame,
    features: pl.DataFrame,
    lookback_secs: int,
) -> pl.DataFrame:
    if features.is_empty():
        return fills.with_columns(
            pl.lit(None).cast(pl.Float64).alias("ofi"),
            pl.lit(None).cast(pl.Float64).alias("spread"),
            pl.lit(None).cast(pl.Datetime).alias("received_at"),
        )
    return fills.sort("timestamp").join_asof(
        features.sort("received_at"),
        left_on="timestamp",
        right_on="received_at",
        left_by="market_id",
        right_by="asset_id",
        strategy="backward",
        tolerance=f"{lookback_secs}s",
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
