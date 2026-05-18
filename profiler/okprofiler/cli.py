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
            lookback_secs=args.lookback_secs,
            min_samples=args.min_samples,
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
    parser.add_argument("--out", default="data/profiler/rules.json")
    parser.add_argument("--lookback-secs", type=int, default=60)
    parser.add_argument("--min-samples", type=int, default=5)
    return parser.parse_args()
