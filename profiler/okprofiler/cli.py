import argparse
import json
from pathlib import Path

from .data_sources import fetch_gamma_markets, fetch_news_rss, fetch_user_trades
from .pipeline import ProfilerConfig, run_profiler


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
    if args.command == "profile":
        profile(args)


def profile(args) -> None:
    result = run_profiler(
        ProfilerConfig(
            fills_path=Path(args.fills),
            clob_path=Path(args.clob),
            news_path=Path(args.news) if args.news else None,
            markets_path=Path(args.markets) if args.markets else None,
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
