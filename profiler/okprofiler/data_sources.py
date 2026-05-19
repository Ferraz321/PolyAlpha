import csv
import json
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
WEATHER_COM_API_KEY = "e1f10a1e78da46f5b10a1e78da96f525"
WEATHER_EVENT_RE = re.compile(
    r"highest-temperature-in-(?P<city>[a-z-]+)-on-(?P<month>[a-z]+)-(?P<day>\d{1,2})-(?P<year>\d{4})"
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


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


def fetch_weather_event_contexts(
    fills: Path,
    out: Path,
    base_url: str = "https://gamma-api.polymarket.com/",
    max_events: int | None = None,
) -> int:
    rows = []
    seen = set()
    for event_slug in _weather_event_slugs(fills)[:max_events]:
        if event_slug in seen:
            continue
        seen.add(event_slug)
        url = urljoin(base_url, "events") + "?" + urlencode({"slug": event_slug})
        event_page = _get_json(url)
        if not event_page:
            rows.append({"event_slug": event_slug, "status": "missing_event"})
            continue
        event = event_page[0]
        rows.extend(_weather_event_rows(event))
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_weather_event_rows(out, rows)
    return len(rows)


def fetch_official_weather_observations(
    contexts: Path,
    out: Path,
    api_key: str = WEATHER_COM_API_KEY,
    max_rows: int | None = None,
) -> int:
    rows = []
    for station_id, event_date in _official_station_dates(contexts)[:max_rows]:
        rows.append(_fetch_official_station_day(station_id, event_date, api_key))
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["official_station_id", "event_date", "official_high_temp_f", "source", "status"]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
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


def resolve_polymarket_user(identifier: str) -> dict:
    handle = _normalize_handle(identifier)
    url = f"https://polymarket.com/@{handle}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 OKTRADER-profiler/0.1"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "ignore")
    proxy_counts: dict[str, int] = {}
    for address in re.findall(r'"proxyWallet":"(0x[a-fA-F0-9]{40})"', html):
        proxy_counts[address.lower()] = proxy_counts.get(address.lower(), 0) + 1
    candidates = proxy_counts or {address.lower(): 1 for address in ADDRESS_RE.findall(html)}
    ranked = sorted(candidates.items(), key=lambda item: item[1], reverse=True)
    wallet = ranked[0][0] if ranked else None
    return {
        "handle": handle,
        "url": url,
        "wallet": wallet,
        "confidence": "high" if proxy_counts and wallet else "low" if wallet else "none",
        "candidates": [{"wallet": address, "count": count} for address, count in ranked[:20]],
    }


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


def _weather_event_slugs(fills: Path) -> list[str]:
    if not fills.exists():
        return []
    slugs = []
    with fills.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            slug = row.get("event_slug")
            if slug and slug.startswith("highest-temperature-in-"):
                slugs.append(slug)
    return list(dict.fromkeys(slugs))


def _official_station_dates(contexts: Path) -> list[tuple[str, str]]:
    if not contexts.exists():
        return []
    pairs = []
    with contexts.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            station = row.get("official_station_id")
            event_date = _event_date_from_slug(row.get("event_slug"))
            if station and event_date:
                pairs.append((station, event_date))
    return list(dict.fromkeys(pairs))


def _event_date_from_slug(slug: str | None) -> str | None:
    if not slug:
        return None
    match = WEATHER_EVENT_RE.search(slug)
    if not match:
        return None
    month = MONTHS.get(match.group("month"))
    if month is None:
        return None
    return f"{int(match.group('year')):04d}-{month:02d}-{int(match.group('day')):02d}"


def _fetch_official_station_day(station_id: str, event_date: str, api_key: str) -> dict:
    date = event_date.replace("-", "")
    url = (
        f"https://api.weather.com/v1/location/{station_id}:9:US/observations/historical.json?"
        + urlencode({"apiKey": api_key, "units": "e", "startDate": date, "endDate": date})
    )
    try:
        payload = _get_json(url)
        observations = payload.get("observations", []) if isinstance(payload, dict) else []
        temps = [_float(row.get("temp")) for row in observations if isinstance(row, dict)]
        temps = [temp for temp in temps if temp is not None]
        return {
            "official_station_id": station_id,
            "event_date": event_date,
            "official_high_temp_f": max(temps) if temps else None,
            "source": f"weather.com:{station_id}",
            "status": "ok" if temps else "missing_temperature",
        }
    except Exception as exc:
        return {
            "official_station_id": station_id,
            "event_date": event_date,
            "official_high_temp_f": None,
            "source": f"weather.com:{station_id}",
            "status": f"error:{type(exc).__name__}",
        }


def _normalize_handle(identifier: str) -> str:
    raw = identifier.strip()
    raw = raw.rsplit("/", 1)[-1] if raw.startswith("http") else raw
    raw = raw.removeprefix("@")
    raw = raw.removeprefix("profile/%40")
    raw = raw.removeprefix("%40")
    return raw


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


def _weather_event_rows(event: dict) -> list[dict]:
    markets = event.get("markets") if isinstance(event.get("markets"), list) else []
    ladder = [_weather_market_context(event, market) for market in markets]
    valid_prices = [row["ladder_yes_price"] for row in ladder if row.get("ladder_yes_price") is not None]
    total = sum(valid_prices) if valid_prices else None
    sorted_prices = sorted(valid_prices)
    for row in ladder:
        price = row.get("ladder_yes_price")
        row["ladder_bucket_count"] = len(ladder)
        row["ladder_price_sum"] = total
        row["ladder_price_rank"] = None if price is None else 1 + sum(1 for value in sorted_prices if value < price)
    return ladder or [
        {
            "event_slug": event.get("slug"),
            "market_slug": None,
            "status": "missing_markets",
            "resolution_source": event.get("resolutionSource"),
            "official_station_id": _station_id(event.get("resolutionSource"), event.get("description")),
            "event_description": event.get("description"),
        }
    ]


def _weather_market_context(event: dict, market: dict) -> dict:
    prices = _json_list(market.get("outcomePrices"))
    yes_price = _float(prices[0]) if prices else None
    source = market.get("resolutionSource") or event.get("resolutionSource")
    description = market.get("description") or event.get("description")
    return {
        "event_slug": event.get("slug"),
        "market_slug": market.get("slug"),
        "status": "ok",
        "resolution_source": source,
        "official_station_id": _station_id(source, description),
        "event_description": description,
        "group_item_title": market.get("groupItemTitle"),
        "ladder_yes_price": yes_price,
        "ladder_best_bid": _float(market.get("bestBid")),
        "ladder_best_ask": _float(market.get("bestAsk")),
        "ladder_last_trade_price": _float(market.get("lastTradePrice")),
        "ladder_market_closed": market.get("closed"),
    }


def _station_id(source: str | None, description: str | None) -> str | None:
    text = " ".join(value for value in [source, description] if value)
    match = re.search(r"/([A-Z]{3,5})(?:[/?#.]|$)", text)
    if match:
        return match.group(1)
    match = re.search(r"\b([A-Z]{4})\b", text)
    return match.group(1) if match else None


def _float(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


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


def _write_weather_event_rows(path: Path, rows: list[dict]) -> None:
    fields = [
        "event_slug",
        "market_slug",
        "status",
        "resolution_source",
        "official_station_id",
        "event_description",
        "group_item_title",
        "ladder_yes_price",
        "ladder_best_bid",
        "ladder_best_ask",
        "ladder_last_trade_price",
        "ladder_market_closed",
        "ladder_bucket_count",
        "ladder_price_sum",
        "ladder_price_rank",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


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
