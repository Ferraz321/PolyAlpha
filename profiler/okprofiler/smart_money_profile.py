from pathlib import Path

import polars as pl

from .factor_discovery import discover_factor_boards, write_factor_discovery
from .factor_discovery_render import render_factor_discovery
from .pipeline import ProfilerConfig, run_profiler


def profile_and_discover(wallet_dir: Path, fills_path: Path, config) -> tuple[str, dict, int]:
    try:
        run_profiler(
            ProfilerConfig(
                fills_path=fills_path,
                clob_path=config.clob_path if config.clob_path and config.clob_path.exists() else wallet_dir / "clob_events.csv",
                news_path=None,
                markets_path=_existing(config.markets_path),
                weather_path=_existing(config.weather_path),
                forecast_path=_existing(config.forecast_path),
                weather_events_path=_existing(config.weather_events_path),
                official_weather_path=_existing(config.official_weather_path),
                marketbridge_context_path=_existing(config.marketbridge_context_path),
                factor_out=wallet_dir / "factor_table.parquet",
                strategy_out=wallet_dir / "strategy_config.json",
                report_out=wallet_dir / "report.md",
                html_out=wallet_dir / "report.html",
                diagnostics_out=wallet_dir / "diagnostics.json",
                factor_summary_out=wallet_dir / "factor_summary.md",
                factor_log_out=wallet_dir / "factor_research_log.md",
                lookback_secs=60,
                min_samples=5,
                research_engines=["core", "agent"],
                validation_out=wallet_dir / "factor_validations.json",
                validation_db=None,
                clusters_out=wallet_dir / "wallet_clusters.json",
                clusters_db=None,
            )
        )
        factor_table = pl.read_parquet(wallet_dir / "factor_table.parquet")
        discovery = discover_factor_boards(
            factor_table,
            [
                "weather_temperature",
                "sector_information_edge",
                "event_news_information_edge",
                "microstructure_liquidity_timing",
                "settlement_timing",
                "marketbridge",
            ],
            max_base_factors=12,
            max_interactions=30,
        )
        discovery["source_factor_table"] = str(wallet_dir / "factor_table.parquet")
        write_factor_discovery(discovery, wallet_dir / "factor_discovery.json")
        (wallet_dir / "factor_discovery.md").write_text(
            render_factor_discovery(discovery, top=10),
            encoding="utf-8",
        )
        effective = sum(
            len(board.get("confirmed_effective", []))
            for board in discovery.get("boards", [])
        )
        return "ok", discovery.get("summary", {}), effective
    except Exception as exc:
        return f"error:{type(exc).__name__}", {}, 0


def _existing(path: Path | None) -> Path | None:
    return path if path and path.exists() else None
