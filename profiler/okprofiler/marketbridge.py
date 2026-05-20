import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


def fetch_marketbridge_context(
    base_url: str,
    out: Path,
    symbols: list[str],
    exchanges: list[str],
    market: str = "perp",
    interval: str = "1m",
    limit: int = 500,
    include_snapshots: bool = False,
) -> int:
    rows = []
    clean_base = base_url.rstrip("/") + "/"
    for exchange in exchanges:
        for symbol in symbols:
            rows.extend(
                _fetch_klines(
                    clean_base,
                    exchange=exchange,
                    market=market,
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                )
            )
    if include_snapshots:
        rows.extend(_fetch_snapshots(clean_base, symbols, exchanges, market))
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["timestamp", "feature", "value", "source"]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _fetch_klines(
    base_url: str,
    exchange: str,
    market: str,
    symbol: str,
    interval: str,
    limit: int,
) -> list[dict]:
    url = urljoin(base_url, "v1/market/klines") + "?" + urlencode(
        {
            "exchange": exchange,
            "market": market,
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
    )
    try:
        payload = _get_json(url)
    except Exception:
        return []
    records = sorted(
        [row for row in _records(payload) if isinstance(row, dict)],
        key=lambda row: _timestamp_sort_key(_first(row, ["timestamp", "ts", "time", "open_time", "openTime", "start"])),
    )
    parsed = []
    for row in records:
        timestamp = _parse_timestamp(
            _first(row, ["timestamp", "ts", "time", "open_time", "openTime", "start"])
        )
        close = _number(_first(row, ["close", "c"]))
        if timestamp is None or close is None:
            continue
        parsed.append(
            {
                "timestamp": timestamp,
                "open": _number(_first(row, ["open", "o"])),
                "high": _number(_first(row, ["high", "h"])),
                "low": _number(_first(row, ["low", "l"])),
                "close": close,
                "volume": _number(_first(row, ["volume", "v", "base_volume"])),
            }
        )
    prefix = _feature_prefix(exchange, market, symbol)
    out = []
    closes = [row["close"] for row in parsed]
    for index, row in enumerate(parsed):
        metrics = {
            "close": row["close"],
            "return_1": _return(closes, index, 1),
            "return_5": _return(closes, index, 5),
            "range_pct": _range_pct(row),
            "volume": row["volume"],
            "volatility_20": _volatility(closes, index, 20),
        }
        for metric, value in metrics.items():
            if value is not None and math.isfinite(float(value)):
                out.append(
                    {
                        "timestamp": row["timestamp"],
                        "feature": f"{prefix}_{metric}",
                        "value": value,
                        "source": "marketbridge:klines",
                    }
                )
    return out


def _fetch_snapshots(
    base_url: str,
    symbols: list[str],
    exchanges: list[str],
    market: str,
) -> list[dict]:
    collected_at = datetime.now(timezone.utc).isoformat()
    rows = []
    symbol_csv = ",".join(symbols)
    exchange_csv = ",".join(exchanges)
    rows.extend(
        _quote_rows(
            _get_json_safe(
                base_url,
                "v1/market/quotes",
                {"symbols": symbol_csv, "exchanges": exchange_csv, "product_type": market},
            ),
            collected_at,
        )
    )
    rows.extend(
        _metric_rows(
            _get_json_safe(base_url, "v1/market/funding", {"symbols": symbol_csv, "exchanges": exchange_csv}),
            collected_at,
            "funding_rate",
            ["funding_rate", "fundingRate", "rate"],
            "marketbridge:funding",
        )
    )
    rows.extend(
        _metric_rows(
            _get_json_safe(base_url, "v1/market/basis", {"symbols": symbol_csv, "exchanges": exchange_csv}),
            collected_at,
            "basis_bps",
            ["basis_bps", "basisBps", "basis"],
            "marketbridge:basis",
        )
    )
    for exchange in exchanges:
        for symbol in symbols:
            rows.extend(
                _order_flow_rows(
                    _get_json_safe(
                        base_url,
                        "v1/market/order-flow",
                        {"exchange": exchange, "market": market, "symbol": symbol},
                    ),
                    collected_at,
                    exchange,
                    market,
                    symbol,
                )
            )
    rows.extend(_external_signal_rows(_get_json_safe(base_url, "v1/external/signals", {}), collected_at))
    return rows


def _quote_rows(payload, timestamp: str) -> list[dict]:
    rows = []
    for record in _records(payload):
        if not isinstance(record, dict):
            continue
        exchange = str(_first(record, ["exchange", "venue", "source"]) or "unknown")
        market = str(_first(record, ["product_type", "market", "kind"]) or "unknown")
        symbol = str(_first(record, ["symbol", "instrument"]) or "unknown")
        prefix = _feature_prefix(exchange, market, symbol)
        bid = _number(_first(record, ["bid", "best_bid", "bid_price"]))
        ask = _number(_first(record, ["ask", "best_ask", "ask_price"]))
        mark = _number(_first(record, ["mark", "mark_price", "last", "price"]))
        mid = (bid + ask) / 2.0 if bid is not None and ask is not None else mark
        for metric, value in {"bid": bid, "ask": ask, "mid": mid, "mark": mark}.items():
            if value is not None:
                rows.append(_row(timestamp, f"{prefix}_{metric}", value, "marketbridge:quotes"))
    return rows


def _metric_rows(payload, timestamp: str, metric: str, keys: list[str], source: str) -> list[dict]:
    rows = []
    for record in _records(payload):
        if not isinstance(record, dict):
            continue
        value = _number(_first(record, keys))
        if value is None:
            continue
        exchange = str(_first(record, ["exchange", "venue", "source"]) or "unknown")
        market = str(_first(record, ["product_type", "market", "kind"]) or "perp")
        symbol = str(_first(record, ["symbol", "instrument"]) or "unknown")
        rows.append(_row(timestamp, f"{_feature_prefix(exchange, market, symbol)}_{metric}", value, source))
    return rows


def _order_flow_rows(payload, timestamp: str, exchange: str, market: str, symbol: str) -> list[dict]:
    prefix = _feature_prefix(exchange, market, symbol)
    rows = []
    for record in _records(payload):
        if not isinstance(record, dict):
            continue
        for metric, keys in {
            "cvd": ["cvd", "cumulative_volume_delta"],
            "buy_volume": ["buy_volume", "buyVolume"],
            "sell_volume": ["sell_volume", "sellVolume"],
            "large_trade_count": ["large_trade_count", "largeTradeCount"],
        }.items():
            value = _number(_first(record, keys))
            if value is not None:
                rows.append(_row(timestamp, f"{prefix}_{metric}", value, "marketbridge:order-flow"))
    return rows


def _external_signal_rows(payload, timestamp: str) -> list[dict]:
    rows = []
    for record in _records(payload):
        if not isinstance(record, dict):
            continue
        source = _sanitize(str(_first(record, ["source", "provider", "name"]) or "external"))
        for key, value in record.items():
            number = _number(value)
            if number is not None:
                rows.append(_row(timestamp, f"mb_external_{source}_{_sanitize(str(key))}", number, "marketbridge:external"))
    return rows


def _get_json_safe(base_url: str, path: str, params: dict):
    try:
        url = urljoin(base_url, path)
        if params:
            url += "?" + urlencode(params)
        return _get_json(url)
    except Exception:
        return None


def _get_json(url: str):
    request = Request(url, headers={"User-Agent": "PolyAlpha-marketbridge/0.1", "Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _records(payload) -> list:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ["data", "rows", "items", "results", "points", "records"]:
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            nested = _records(value)
            if nested:
                return nested
    return [payload]


def _row(timestamp: str, feature: str, value: float, source: str) -> dict:
    return {"timestamp": timestamp, "feature": feature, "value": value, "source": source}


def _first(row: dict, keys: list[str]):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _number(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _parse_timestamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value) / 1000.0 if value > 10_000_000_000 else float(value)
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
    text = str(value)
    if text.isdigit():
        return _parse_timestamp(int(text))
    return text


def _timestamp_sort_key(value) -> str:
    return _parse_timestamp(value) or ""


def _return(values: list[float], index: int, lag: int) -> float | None:
    if index < lag or values[index - lag] == 0.0:
        return None
    return values[index] / values[index - lag] - 1.0


def _range_pct(row: dict) -> float | None:
    high = row.get("high")
    low = row.get("low")
    close = row.get("close")
    if high is None or low is None or close in (None, 0.0):
        return None
    return (high - low) / close


def _volatility(values: list[float], index: int, window: int) -> float | None:
    if index < window:
        return None
    returns = [
        _return(values, offset, 1)
        for offset in range(index - window + 1, index + 1)
    ]
    returns = [value for value in returns if value is not None]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def _feature_prefix(exchange: str, market: str, symbol: str) -> str:
    return f"mb_{_sanitize(exchange)}_{_sanitize(market)}_{_sanitize(symbol)}"


def _sanitize(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")
