import csv
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
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
