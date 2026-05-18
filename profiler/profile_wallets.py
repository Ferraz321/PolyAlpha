#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
from sklearn.neighbors import KernelDensity


def main() -> None:
    args = parse_args()
    fills = pl.read_csv(args.fills, try_parse_dates=True)
    clob = pl.read_csv(args.clob, try_parse_dates=True)
    if fills.is_empty():
        raise SystemExit("no fills to profile")

    features = extract_clob_features(clob)
    joined = fills.sort("timestamp").join_asof(
        features.sort("received_at"),
        left_on="timestamp",
        right_on="received_at",
        left_by="market_id",
        right_by="asset_id",
        strategy="backward",
        tolerance=f"{args.lookback_secs}s",
    )
    rules = build_rules(joined)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rules, indent=2), encoding="utf-8")
    print(json.dumps(rules, indent=2))


def extract_clob_features(clob: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for row in clob.iter_rows(named=True):
        try:
            payload = json.loads(row["payload"])
        except Exception:
            continue
        rows.extend(features_from_payload(row, payload))
    return pl.DataFrame(rows) if rows else empty_features()


def features_from_payload(row: dict, payload) -> list[dict]:
    payloads = payload if isinstance(payload, list) else [payload]
    out = []
    for item in payloads:
        event_type = item.get("event_type")
        if event_type == "price_change":
            for change in item.get("price_changes", []):
                out.append(feature(row, item.get("market"), change, event_type))
        elif event_type in {"best_bid_ask", "last_trade_price"}:
            out.append(feature(row, item.get("market"), item, event_type))
        elif event_type == "book":
            out.append(book_feature(row, item))
    return [item for item in out if item.get("asset_id")]


def feature(row: dict, market: str | None, item: dict, event_type: str) -> dict:
    bid = to_float(item.get("best_bid"))
    ask = to_float(item.get("best_ask"))
    size = to_float(item.get("size")) or 0.0
    side = item.get("side")
    return {
        "asset_id": item.get("asset_id"),
        "market": market,
        "received_at": row["received_at"],
        "event_type": event_type,
        "spread": None if bid is None or ask is None else ask - bid,
        "ofi": size if side == "BUY" else -size if side == "SELL" else 0.0,
    }


def book_feature(row: dict, item: dict) -> dict:
    bids = item.get("bids", [])
    asks = item.get("asks", [])
    bid_depth = sum(to_float(level.get("size")) or 0.0 for level in bids)
    ask_depth = sum(to_float(level.get("size")) or 0.0 for level in asks)
    total = bid_depth + ask_depth
    return {
        "asset_id": item.get("asset_id"),
        "market": item.get("market"),
        "received_at": row["received_at"],
        "event_type": "book",
        "spread": None,
        "ofi": 0.0 if total == 0 else (bid_depth - ask_depth) / total,
    }


def build_rules(joined: pl.DataFrame) -> dict:
    numeric = joined.select(pl.col("ofi").drop_nulls()).to_series().to_numpy()
    threshold = float(np.quantile(numeric, 0.90)) if len(numeric) else 0.0
    kde_peak = kde_mode(numeric) if len(numeric) >= 5 else 0.0
    return {
        "rows": joined.height,
        "ofi_p90": threshold,
        "ofi_kde_mode": kde_peak,
        "rule": f"consider BUY pressure when ofi > {threshold:.4f}",
    }


def kde_mode(values: np.ndarray) -> float:
    values = values.reshape(-1, 1)
    kde = KernelDensity(kernel="gaussian", bandwidth=max(np.std(values), 1e-6)).fit(values)
    grid = np.linspace(values.min(), values.max(), 200).reshape(-1, 1)
    return float(grid[np.argmax(kde.score_samples(grid))][0])


def empty_features() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "market": pl.Utf8,
            "received_at": pl.Datetime,
            "event_type": pl.Utf8,
            "spread": pl.Float64,
            "ofi": pl.Float64,
        }
    )


def to_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except Exception:
        return None


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fills", default="data/profiler/fills.csv")
    parser.add_argument("--clob", default="data/profiler/clob_events.csv")
    parser.add_argument("--out", default="data/profiler/rules.json")
    parser.add_argument("--lookback-secs", type=int, default=60)
    return parser.parse_args()


if __name__ == "__main__":
    main()
