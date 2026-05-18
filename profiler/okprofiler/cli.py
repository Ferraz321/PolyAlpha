import argparse
import json
from pathlib import Path

from .pipeline import ProfilerConfig, run_profiler


def main() -> None:
    args = parse_args()
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
    parser.add_argument("--fills", default="data/profiler/fills.csv")
    parser.add_argument("--clob", default="data/profiler/clob_events.csv")
    parser.add_argument("--news")
    parser.add_argument("--markets")
    parser.add_argument("--out", default="data/profiler/rules.json")
    parser.add_argument("--factor-out", default="data/profiler/factor_table.parquet")
    parser.add_argument("--strategy-out", default="data/profiler/strategy_config.json")
    parser.add_argument("--report-out", default="data/profiler/report.md")
    parser.add_argument("--html-out", default="data/profiler/report.html")
    parser.add_argument("--lookback-secs", type=int, default=60)
    parser.add_argument("--min-samples", type=int, default=5)
    parser.add_argument(
        "--research-engines",
        default="core,alphalens,shap,stumpy,agent",
        help="comma-separated engines: core,alphalens,shap,stumpy,nautilus,agent",
    )
    return parser.parse_args()


def _parse_engines(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]
