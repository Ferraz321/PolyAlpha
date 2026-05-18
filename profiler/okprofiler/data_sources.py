import csv
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


def fetch_gamma_markets(
    out: Path,
    base_url: str = "https://gamma-api.polymarket.com/",
    limit: int = 500,
    max_offset: int = 5000,
) -> int:
    rows = []
    for offset in range(0, max_offset + 1, limit):
        url = urljoin(base_url, "markets") + "?" + urlencode({"limit": limit, "offset": offset})
        page = _get_json(url)
        if not page:
            break
        for market in page:
            rows.extend(_market_rows(market))
        if len(page) < limit:
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_rows(out, rows)
    return len(rows)


def fetch_news_rss(out: Path, url: str) -> int:
    request = Request(url, headers={"User-Agent": "OKTRADER-profiler/0.1"})
    with urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())
    rows = []
    for item in root.findall(".//item"):
        title = _xml_text(item, "title")
        published = _parse_rss_time(_xml_text(item, "pubDate"))
        rows.append(
            {
                "published_at": published,
                "last_news_slug": _slug(title),
                "title": title,
                "url": _xml_text(item, "link"),
            }
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["published_at", "last_news_slug", "title", "url"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def fetch_user_trades(
    wallet: str,
    out: Path,
    base_url: str = "https://data-api.polymarket.com/",
    limit: int = 500,
    max_offset: int = 5000,
) -> int:
    rows = []
    for offset in range(0, max_offset + 1, limit):
        params = {"user": wallet, "limit": limit, "offset": offset}
        url = urljoin(base_url, "trades") + "?" + urlencode(params)
        page = _get_json(url)
        if not page:
            break
        rows.extend(_trade_rows(page))
        if len(page) < limit:
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_fills(out, rows)
    return len(rows)


def assets_from_fills(fills: Path, out: Path, limit: int | None = None) -> int:
    seen = []
    with fills.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            asset = row.get("market_id") or row.get("asset")
            if not asset or asset in seen:
                continue
            seen.append(asset)
            if limit is not None and len(seen) >= limit:
                break
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(seen) + ("\n" if seen else ""), encoding="utf-8")
    return len(seen)


def _get_json(url: str):
    request = Request(
        url,
        headers={
            "User-Agent": "OKTRADER-profiler/0.1",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _trade_rows(page: list[dict]) -> list[dict]:
    rows = []
    for trade in page:
        wallet = trade.get("proxyWallet") or trade.get("user")
        asset = trade.get("asset")
        if not wallet or not asset:
            continue
        rows.append(
            {
                "account": str(wallet).lower(),
                "market_id": str(asset),
                "condition_id": trade.get("conditionId"),
                "event_slug": trade.get("eventSlug"),
                "market_slug": trade.get("slug"),
                "title": trade.get("title"),
                "outcome": trade.get("outcome"),
                "sector": None,
                "side": str(trade.get("side", "")).lower(),
                "role": "taker",
                "price": trade.get("price"),
                "shares": trade.get("size"),
                "timestamp": _unix_to_iso(trade.get("timestamp")),
                "tx_hash": trade.get("transactionHash"),
                "order_hash": None,
            }
        )
    return rows


def _write_fills(path: Path, rows: list[dict]) -> None:
    fields = [
        "account",
        "market_id",
        "condition_id",
        "event_slug",
        "market_slug",
        "title",
        "outcome",
        "sector",
        "side",
        "role",
        "price",
        "shares",
        "timestamp",
        "tx_hash",
        "order_hash",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _unix_to_iso(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _market_rows(market: dict) -> list[dict]:
    token_ids = _json_list(market.get("clobTokenIds"))
    outcomes = _json_list(market.get("outcomes"))
    rows = []
    for idx, asset_id in enumerate(token_ids):
        rows.append(
            {
                "asset_id": str(asset_id),
                "condition_id": market.get("conditionId") or market.get("condition_id"),
                "market_slug": market.get("slug"),
                "event_slug": _event_slug(market),
                "question": market.get("question"),
                "outcome": outcomes[idx] if idx < len(outcomes) else None,
                "resolution_time": market.get("endDate") or market.get("end_date"),
                "sector": _sector(market),
            }
        )
    return rows


def _json_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        decoded = json.loads(value)
        return decoded if isinstance(decoded, list) else []
    except Exception:
        return []


def _event_slug(market: dict) -> str | None:
    events = market.get("events")
    if isinstance(events, list) and events:
        return events[0].get("slug")
    return market.get("eventSlug") or market.get("event_slug")


def _sector(market: dict) -> str | None:
    tags = market.get("tags")
    if isinstance(tags, list) and tags:
        first = tags[0]
        return first.get("label") if isinstance(first, dict) else str(first)
    return market.get("category")


def _write_rows(path: Path, rows: list[dict]) -> None:
    fields = ["asset_id", "condition_id", "market_slug", "event_slug", "question", "outcome", "resolution_time", "sector"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _xml_text(item, tag: str) -> str | None:
    found = item.find(tag)
    return None if found is None or found.text is None else found.text.strip()


def _parse_rss_time(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def _slug(value: str | None) -> str | None:
    if value is None:
        return None
    return "-".join(value.lower().replace("?", "").replace(",", "").split())[:120]
