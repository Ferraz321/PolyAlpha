import json

import polars as pl


def extract_clob_features(clob: pl.DataFrame) -> pl.DataFrame:
    rows = []
    for row in clob.iter_rows(named=True):
        try:
            payload = json.loads(row["payload"])
        except Exception:
            continue
        rows.extend(_features_from_payload(row, payload))
    return pl.DataFrame(rows) if rows else empty_features()


def empty_features() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "asset_id": pl.Utf8,
            "market": pl.Utf8,
            "received_at": pl.Datetime,
            "event_type": pl.Utf8,
            "spread": pl.Float64,
            "ofi": pl.Float64,
            "best_bid": pl.Float64,
            "best_ask": pl.Float64,
            "mid_price": pl.Float64,
            "bid_depth": pl.Float64,
            "ask_depth": pl.Float64,
            "depth_imbalance": pl.Float64,
            "trade_size": pl.Float64,
        }
    )


def _features_from_payload(row: dict, payload) -> list[dict]:
    payloads = payload if isinstance(payload, list) else [payload]
    out = []
    for item in payloads:
        event_type = item.get("event_type")
        if event_type == "price_change":
            for change in item.get("price_changes", []):
                out.append(_tick_feature(row, item.get("market"), change, event_type))
        elif event_type in {"best_bid_ask", "last_trade_price"}:
            out.append(_tick_feature(row, item.get("market"), item, event_type))
        elif event_type == "book":
            out.append(_book_feature(row, item))
    return [item for item in out if item.get("asset_id")]


def _tick_feature(row: dict, market: str | None, item: dict, event_type: str) -> dict:
    bid = _to_float(item.get("best_bid"))
    ask = _to_float(item.get("best_ask"))
    size = _to_float(item.get("size")) or 0.0
    side = item.get("side")
    return {
        "asset_id": item.get("asset_id"),
        "market": market,
        "received_at": row["received_at"],
        "event_type": event_type,
        "spread": None if bid is None or ask is None else ask - bid,
        "ofi": size if side == "BUY" else -size if side == "SELL" else 0.0,
        "best_bid": bid,
        "best_ask": ask,
        "mid_price": _mid_price(bid, ask),
        "bid_depth": None,
        "ask_depth": None,
        "depth_imbalance": None,
        "trade_size": size,
    }


def _book_feature(row: dict, item: dict) -> dict:
    bids = item.get("bids", [])
    asks = item.get("asks", [])
    bid_depth = sum(_to_float(level.get("size")) or 0.0 for level in bids)
    ask_depth = sum(_to_float(level.get("size")) or 0.0 for level in asks)
    total = bid_depth + ask_depth
    best_bid = max((_to_float(level.get("price")) or 0.0 for level in bids), default=None)
    best_ask = min((_to_float(level.get("price")) or 1.0 for level in asks), default=None)
    return {
        "asset_id": item.get("asset_id"),
        "market": item.get("market"),
        "received_at": row["received_at"],
        "event_type": "book",
        "spread": None if best_bid is None or best_ask is None else best_ask - best_bid,
        "ofi": 0.0 if total == 0 else (bid_depth - ask_depth) / total,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": _mid_price(best_bid, best_ask),
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "depth_imbalance": 0.0 if total == 0 else (bid_depth - ask_depth) / total,
        "trade_size": 0.0,
    }


def _to_float(value) -> float | None:
    try:
        return None if value is None else float(value)
    except Exception:
        return None


def _mid_price(bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2.0
