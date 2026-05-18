import argparse
import json
from pathlib import Path

from .agent import AgentConfig, run_agent
from .data_sources import (
    assets_from_fills,
    fetch_gamma_markets,
    fetch_news_rss,
    fetch_user_trades,
    resolve_polymarket_user,
)
from .pipeline import ProfilerConfig, run_profiler
from .weather_sources import fetch_open_meteo_archive
from .weather_sources import fetch_open_meteo_forecast_history


def main() -> None:
    args = parse_args()
    if args.command == "fetch-gamma-markets":
        rows = fetch_gamma_markets(
            out=Path(args.out),
            base_url=args.gamma_base_url,
            limit=args.limit,
            max_offset=args.max_offset,
        )
        print(json.dumps({"markets_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "fetch-news-rss":
        rows = fetch_news_rss(out=Path(args.out), url=args.url)
        print(json.dumps({"news_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "fetch-user-trades":
        rows = fetch_user_trades(
            wallet=args.wallet,
            out=Path(args.out),
            limit=args.limit,
            max_offset=args.max_offset,
        )
        print(json.dumps({"trade_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "resolve-user":
        result = resolve_polymarket_user(args.user)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return
    if args.command == "research-user":
        research_user(args)
        return
    if args.command == "assets-from-fills":
        rows = assets_from_fills(
            fills=Path(args.fills),
            out=Path(args.out),
            limit=args.limit,
        )
        print(json.dumps({"asset_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "fetch-weather-open-meteo":
        rows = fetch_open_meteo_archive(
            profile_dir=Path(args.profile_dir),
            locations_csv=Path(args.locations_csv),
            out=Path(args.out),
        )
        print(json.dumps({"weather_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "fetch-weather-forecast-history":
        rows = fetch_open_meteo_forecast_history(
            profile_dir=Path(args.profile_dir),
            locations_csv=Path(args.locations_csv),
            out=Path(args.out),
        )
        print(json.dumps({"forecast_rows": rows, "out": args.out}, indent=2))
        return
    if args.command == "agent":
        agent(args)
        return
    if args.command == "profile":
        profile(args)


def profile(args) -> None:
    result = run_profiler(
        ProfilerConfig(
            fills_path=Path(args.fills),
            clob_path=Path(args.clob),
            news_path=Path(args.news) if args.news else None,
            markets_path=Path(args.markets) if args.markets else None,
            weather_path=Path(args.weather) if args.weather else None,
            forecast_path=Path(args.forecast) if args.forecast else None,
            factor_out=Path(args.factor_out) if args.factor_out else None,
            strategy_out=Path(args.strategy_out) if args.strategy_out else None,
            report_out=Path(args.report_out) if args.report_out else None,
            html_out=Path(args.html_out) if args.html_out else None,
            diagnostics_out=Path(args.diagnostics_out) if args.diagnostics_out else None,
            factor_summary_out=Path(args.factor_summary_out) if args.factor_summary_out else None,
            factor_log_out=Path(args.factor_log_out) if args.factor_log_out else None,
            lookback_secs=args.lookback_secs,
            min_samples=args.min_samples,
            research_engines=_parse_engines(args.research_engines),
        )
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def agent(args) -> None:
    profile_dir = Path(args.profile_dir)
    wallet_pool = args.wallet_pool
    if wallet_pool is None and (profile_dir / "wallet_pool.txt").exists():
        wallet_pool = str(profile_dir / "wallet_pool.txt")
    result = run_agent(
        AgentConfig(
            profile_dir=profile_dir,
            rules_path=Path(args.rules) if args.rules else profile_dir / "rules.json",
            diagnostics_path=Path(args.diagnostics) if args.diagnostics else profile_dir / "diagnostics.json",
            report_out=Path(args.report_out) if args.report_out else profile_dir / "research_report.md",
            candidates_out=Path(args.candidates_out) if args.candidates_out else profile_dir / "candidate_factors.json",
            next_commands_out=Path(args.next_commands_out) if args.next_commands_out else profile_dir / "next_commands.json",
            sop_status_out=Path(args.sop_status_out) if args.sop_status_out else profile_dir / "sop_status.json",
            sop_path=Path(args.sop_path),
            candidate_library=Path(args.candidate_library),
            db=Path(args.db),
            wallets=_parse_wallets(args.wallet, wallet_pool),
            rerun_profile=args.rerun_profile,
            run_tools=args.run_tools,
            launch_watch_clob=args.launch_watch_clob,
            update_candidates=args.update_candidates,
            research_engines=_parse_engines(args.research_engines),
            min_samples=args.min_samples,
            trades_limit=args.trades_limit,
            trades_max_offset=args.trades_max_offset,
            gamma_limit=args.gamma_limit,
            gamma_max_offset=args.gamma_max_offset,
        )
    )
    print(json.dumps(result, indent=2))


def research_user(args) -> None:
    resolved = resolve_polymarket_user(args.user)
    if not resolved.get("wallet"):
        raise SystemExit(f"could not resolve Polymarket user: {args.user}")
    profile_dir = Path(args.profile_dir or f"data/profiler_{resolved['handle']}")
    result = run_agent(
        AgentConfig(
            profile_dir=profile_dir,
            rules_path=profile_dir / "rules.json",
            diagnostics_path=profile_dir / "diagnostics.json",
            report_out=profile_dir / "research_report.md",
            candidates_out=profile_dir / "candidate_factors.json",
            next_commands_out=profile_dir / "next_commands.json",
            sop_status_out=profile_dir / "sop_status.json",
            sop_path=Path(args.sop_path),
            candidate_library=Path(args.candidate_library),
            db=Path(args.db),
            wallets=[resolved["wallet"]],
            rerun_profile=False,
            run_tools=True,
            launch_watch_clob=args.launch_watch_clob,
            update_candidates=args.update_candidates,
            research_engines=_parse_engines(args.research_engines),
            min_samples=args.min_samples,
        )
    )
    result["resolved_user"] = resolved
    (profile_dir / "resolved_user.json").write_text(json.dumps(resolved, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    profile_parser = subparsers.add_parser("profile")
    _add_profile_args(profile_parser)
    fetch = subparsers.add_parser("fetch-gamma-markets")
    fetch.add_argument("--out", default="data/profiler/markets.csv")
    fetch.add_argument("--gamma-base-url", default="https://gamma-api.polymarket.com/")
    fetch.add_argument("--limit", type=int, default=500)
    fetch.add_argument("--max-offset", type=int, default=5000)
    news = subparsers.add_parser("fetch-news-rss")
    news.add_argument("--url", required=True)
    news.add_argument("--out", default="data/profiler/news.csv")
    trades = subparsers.add_parser("fetch-user-trades")
    trades.add_argument("--wallet", required=True)
    trades.add_argument("--out", default="data/profiler/fills.csv")
    trades.add_argument("--limit", type=int, default=500)
    trades.add_argument("--max-offset", type=int, default=5000)
    resolve = subparsers.add_parser("resolve-user")
    resolve.add_argument("user")
    resolve.add_argument("--out")
    research_user_parser = subparsers.add_parser("research-user")
    research_user_parser.add_argument("user")
    research_user_parser.add_argument("--profile-dir")
    research_user_parser.add_argument("--db", default="data/oktrader.sqlite")
    research_user_parser.add_argument("--candidate-library", default="docs/candidate_factors.json")
    research_user_parser.add_argument("--sop-path", default="config/agent_sop.json")
    research_user_parser.add_argument("--update-candidates", action="store_true")
    research_user_parser.add_argument("--launch-watch-clob", action="store_true")
    research_user_parser.add_argument("--min-samples", type=int, default=5)
    research_user_parser.add_argument("--trades-limit", type=int, default=500)
    research_user_parser.add_argument("--trades-max-offset", type=int, default=5000)
    research_user_parser.add_argument("--gamma-limit", type=int, default=500)
    research_user_parser.add_argument("--gamma-max-offset", type=int, default=5000)
    research_user_parser.add_argument(
        "--research-engines",
        default="core,alphalens,shap,stumpy,agent",
    )
    assets = subparsers.add_parser("assets-from-fills")
    assets.add_argument("--fills", default="data/profiler/fills.csv")
    assets.add_argument("--out", default="data/clob_assets.txt")
    assets.add_argument("--limit", type=int)
    weather = subparsers.add_parser("fetch-weather-open-meteo")
    weather.add_argument("--profile-dir", default="data/profiler")
    weather.add_argument("--locations-csv", default="config/weather_locations.csv")
    weather.add_argument("--out", default="data/profiler/weather_observations.csv")
    forecast = subparsers.add_parser("fetch-weather-forecast-history")
    forecast.add_argument("--profile-dir", default="data/profiler")
    forecast.add_argument("--locations-csv", default="config/weather_locations.csv")
    forecast.add_argument("--out", default="data/profiler/forecast_history.csv")
    agent_parser = subparsers.add_parser("agent")
    agent_parser.add_argument("--profile-dir", default="data/profiler")
    agent_parser.add_argument("--db", default="data/oktrader.sqlite")
    agent_parser.add_argument("--wallet", action="append", default=[])
    agent_parser.add_argument("--wallet-pool")
    agent_parser.add_argument("--rules")
    agent_parser.add_argument("--diagnostics")
    agent_parser.add_argument("--report-out")
    agent_parser.add_argument("--candidates-out")
    agent_parser.add_argument("--next-commands-out")
    agent_parser.add_argument("--sop-status-out")
    agent_parser.add_argument("--sop-path", default="config/agent_sop.json")
    agent_parser.add_argument("--candidate-library", default="docs/candidate_factors.json")
    agent_parser.add_argument("--rerun-profile", action="store_true")
    agent_parser.add_argument("--run-tools", action="store_true")
    agent_parser.add_argument("--launch-watch-clob", action="store_true")
    agent_parser.add_argument("--update-candidates", action="store_true")
    agent_parser.add_argument("--min-samples", type=int, default=5)
    agent_parser.add_argument("--trades-limit", type=int, default=500)
    agent_parser.add_argument("--trades-max-offset", type=int, default=5000)
    agent_parser.add_argument("--gamma-limit", type=int, default=500)
    agent_parser.add_argument("--gamma-max-offset", type=int, default=5000)
    agent_parser.add_argument(
        "--research-engines",
        default="core,alphalens,shap,stumpy,agent",
        help="comma-separated engines used when --rerun-profile is set",
    )
    _add_profile_args(parser)
    args = parser.parse_args()
    if args.command is None:
        args.command = "profile"
    return args


def _add_profile_args(parser):
    parser.add_argument("--fills", default="data/profiler/fills.csv")
    parser.add_argument("--clob", default="data/profiler/clob_events.csv")
    parser.add_argument("--news")
    parser.add_argument("--markets")
    parser.add_argument("--weather")
    parser.add_argument("--forecast")
    parser.add_argument("--out", default="data/profiler/rules.json")
    parser.add_argument("--factor-out", default="data/profiler/factor_table.parquet")
    parser.add_argument("--strategy-out", default="data/profiler/strategy_config.json")
    parser.add_argument("--report-out", default="data/profiler/report.md")
    parser.add_argument("--html-out", default="data/profiler/report.html")
    parser.add_argument("--diagnostics-out", default="data/profiler/diagnostics.json")
    parser.add_argument("--factor-summary-out", default="data/profiler/factor_summary.md")
    parser.add_argument("--factor-log-out", default="data/profiler/factor_research_log.md")
    parser.add_argument("--lookback-secs", type=int, default=60)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument(
        "--research-engines",
        default="core,alphalens,shap,stumpy,agent",
        help="comma-separated engines: core,alphalens,shap,stumpy,nautilus,agent",
    )


def _parse_engines(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _parse_wallets(raw_wallets: list[str], wallet_pool: str | None) -> list[str]:
    wallets = list(raw_wallets or [])
    if wallet_pool:
        path = Path(wallet_pool)
        if path.exists():
            wallets.extend(
                line.strip().split(",", 1)[0]
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
    return list(dict.fromkeys(wallets))
