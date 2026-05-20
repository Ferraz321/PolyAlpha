import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

import polars as pl

from .smart_money_profile import profile_and_discover
from .smart_money_render import render_smart_money_archive


@dataclass(frozen=True)
class SmartMoneyScanConfig:
    base_url: str
    out_dir: Path
    page_size: int = 500
    max_offset: int = 1000
    max_wallets: int = 10
    min_trade_notional: float = 10_000.0
    history_limit: int = 500
    history_max_offset: int = 2000
    min_history_rows: int = 50
    markets_path: Path | None = None
    clob_path: Path | None = None
    weather_path: Path | None = None
    forecast_path: Path | None = None
    weather_events_path: Path | None = None
    official_weather_path: Path | None = None
    marketbridge_context_path: Path | None = None
    seed_wallets: tuple[str, ...] = ()
    profile_wallets: bool = True


def scan_smart_money(config: SmartMoneyScanConfig) -> dict:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    recent_rows = _fetch_recent_trades(config)
    _write_fills(config.out_dir / "recent_fills.csv", recent_rows)
    candidates = _rank_recent_candidates(recent_rows, config)
    candidates = _merge_seed_wallets(candidates, config.seed_wallets)
    wallet_records = []
    for candidate in candidates[: config.max_wallets]:
        wallet_records.append(_research_wallet(candidate, config))
    result = {
        "version": 1,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "base_url": config.base_url,
        "recent_trade_rows": len(recent_rows),
        "candidate_count": len(candidates),
        "archived_wallet_count": len(wallet_records),
        "research_ready_count": sum(1 for row in wallet_records if row["archive_status"] == "research_ready"),
        "wallets": wallet_records,
    }
    _write_json(config.out_dir / "smart_money_archive.json", result)
    _write_markdown(config.out_dir / "smart_money_archive.md", result)
    return result


def _research_wallet(candidate: dict, config: SmartMoneyScanConfig) -> dict:
    wallet = candidate["account"]
    wallet_dir = config.out_dir / "wallets" / wallet
    wallet_dir.mkdir(parents=True, exist_ok=True)
    history_rows = _fetch_wallet_history(wallet, config)
    fills_path = wallet_dir / "fills.csv"
    _write_fills(fills_path, history_rows)
    history_metrics = _wallet_metrics(history_rows)
    classification = _classify(history_metrics)
    profile_status = "skipped"
    discovery_summary = {}
    effective_count = 0
    if config.profile_wallets and len(history_rows) >= config.min_history_rows:
        profile_status, discovery_summary, effective_count = profile_and_discover(
            wallet_dir,
            fills_path,
            config,
        )
    archive_status = _archive_status(history_rows, classification, profile_status, effective_count)
    record = {
        **candidate,
        "smart_money_score": candidate.get("recent_score", 0.0),
        "archive_status": archive_status,
        "history_rows": len(history_rows),
        "history_metrics": history_metrics,
        "classification": classification,
        "profile_status": profile_status,
        "factor_discovery_summary": discovery_summary,
        "effective_factor_count": effective_count,
        "wallet_dir": str(wallet_dir),
    }
    _write_json(wallet_dir / "archive_record.json", record)
    return record

def _fetch_recent_trades(config: SmartMoneyScanConfig) -> list[dict]:
    rows = []
    for offset in range(0, config.max_offset + 1, config.page_size):
        page = _get_trades(config.base_url, {"limit": config.page_size, "offset": offset})
        if not page:
            break
        rows.extend(_trade_rows(page))
        if len(page) < config.page_size:
            break
    return rows


def _fetch_wallet_history(wallet: str, config: SmartMoneyScanConfig) -> list[dict]:
    rows = []
    for offset in range(0, config.history_max_offset + 1, config.history_limit):
        page = _get_trades(
            config.base_url,
            {"user": wallet, "limit": config.history_limit, "offset": offset},
        )
        if not page:
            break
        rows.extend(_trade_rows(page))
        if len(page) < config.history_limit:
            break
    return rows


def _rank_recent_candidates(rows: list[dict], config: SmartMoneyScanConfig) -> list[dict]:
    by_wallet = defaultdict(list)
    for row in rows:
        by_wallet[row["account"]].append(row)
    candidates = []
    for wallet, wallet_rows in by_wallet.items():
        metrics = _wallet_metrics(wallet_rows)
        large_trades = [row for row in wallet_rows if _notional(row) >= config.min_trade_notional]
        if not large_trades:
            continue
        score = _recent_score(metrics, large_trades)
        candidates.append(
            {
                "account": wallet,
                "recent_score": score,
                "recent_trade_count": len(wallet_rows),
                "recent_large_trade_count": len(large_trades),
                "recent_total_volume": metrics["total_volume"],
                "recent_max_trade_notional": max(_notional(row) for row in wallet_rows),
                "recent_distinct_markets": metrics["distinct_markets"],
            }
        )
    return sorted(candidates, key=lambda row: row["recent_score"], reverse=True)


def _merge_seed_wallets(candidates: list[dict], seed_wallets: tuple[str, ...]) -> list[dict]:
    seen = {row["account"] for row in candidates}
    merged = list(candidates)
    for wallet in seed_wallets:
        normalized = wallet.strip().lower()
        if not normalized or normalized in seen:
            continue
        merged.append(
            {
                "account": normalized,
                "recent_score": 0.0,
                "recent_trade_count": 0,
                "recent_large_trade_count": 0,
                "recent_total_volume": 0.0,
                "recent_max_trade_notional": 0.0,
                "recent_distinct_markets": 0,
                "seed_wallet": True,
            }
        )
        seen.add(normalized)
    return merged


def _wallet_metrics(rows: list[dict]) -> dict:
    if not rows:
        return _empty_metrics()
    total_volume = sum(_notional(row) for row in rows)
    by_market = defaultdict(list)
    for row in rows:
        by_market[row["market_id"]].append(row)
    loops = [_closed_loop(market_rows) for market_rows in by_market.values()]
    loops = [loop for loop in loops if loop is not None]
    wins = [loop["pnl"] for loop in loops if loop["pnl"] > 0]
    losses = [-loop["pnl"] for loop in loops if loop["pnl"] < 0]
    total_pnl = sum(loop["pnl"] for loop in loops)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    max_win = max(wins) if wins else 0.0
    return {
        "trade_count": len(rows),
        "distinct_markets": len(by_market),
        "closed_markets": len(loops),
        "total_volume": total_volume,
        "avg_trade_size": total_volume / len(rows),
        "total_pnl": total_pnl,
        "win_rate": len(wins) / len(loops) if loops else 0.0,
        "profit_loss_ratio": avg_win / avg_loss if avg_loss > 0 else 0.0,
        "max_single_market_pnl_share": max_win / total_pnl if total_pnl > 0 else 0.0,
    }


def _closed_loop(rows: list[dict]) -> dict | None:
    buy_shares = sum(_float(row["shares"]) for row in rows if row["side"] == "buy")
    sell_shares = sum(_float(row["shares"]) for row in rows if row["side"] == "sell")
    if buy_shares <= 0 or sell_shares < 0.95 * buy_shares:
        return None
    buy_notional = sum(_notional(row) for row in rows if row["side"] == "buy")
    sell_notional = sum(_notional(row) for row in rows if row["side"] == "sell")
    return {"pnl": sell_notional - buy_notional}


def _classify(metrics: dict) -> str:
    if metrics["trade_count"] < 30 or metrics["closed_markets"] < 3:
        return "small_sample_watchlist"
    if metrics["total_pnl"] < 0:
        return "unprofitable"
    if metrics["max_single_market_pnl_share"] >= 0.60 and metrics["total_pnl"] >= 10_000:
        return "one_shot_whale"
    if (
        metrics["trade_count"] >= 150
        and metrics["closed_markets"] >= 15
        and metrics["total_volume"] >= 100_000
        and metrics["total_pnl"] >= 10_000
        and metrics["win_rate"] >= 0.60
        and metrics["max_single_market_pnl_share"] < 0.60
    ):
        return "candidate_smart_money"
    if metrics["total_volume"] >= 100_000 and metrics["trade_count"] >= 30:
        return "whale_watchlist"
    return "research_watchlist"


def _archive_status(rows: list[dict], classification: str, profile_status: str, effective_count: int) -> str:
    if len(rows) == 0:
        return "blocked_no_history"
    if profile_status.startswith("error"):
        return "blocked_profile_error"
    if (
        profile_status == "ok"
        and effective_count > 0
        and classification not in {"small_sample_watchlist", "unprofitable", "one_shot_whale"}
    ):
        return "research_ready"
    if classification == "candidate_smart_money" and effective_count > 0:
        return "research_ready"
    if classification in {"whale_watchlist", "research_watchlist"}:
        return "watchlist"
    return "rejected_or_waiting"


def _recent_score(metrics: dict, large_trades: list[dict]) -> float:
    volume_score = min(metrics["total_volume"] / 250_000.0, 1.0)
    activity_score = min(metrics["trade_count"] / 100.0, 1.0)
    whale_score = min(len(large_trades) / 10.0, 1.0)
    market_score = min(metrics["distinct_markets"] / 10.0, 1.0)
    return round(0.35 * volume_score + 0.25 * activity_score + 0.25 * whale_score + 0.15 * market_score, 6)


def _empty_metrics() -> dict:
    return {
        "trade_count": 0,
        "distinct_markets": 0,
        "closed_markets": 0,
        "total_volume": 0.0,
        "avg_trade_size": 0.0,
        "total_pnl": 0.0,
        "win_rate": 0.0,
        "profit_loss_ratio": 0.0,
        "max_single_market_pnl_share": 0.0,
    }


def _get_trades(base_url: str, params: dict) -> list[dict]:
    url = urljoin(base_url.rstrip("/") + "/", "trades") + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": "PolyAlpha-smart-money/0.1", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, list) else []


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
        "account", "market_id", "condition_id", "event_slug", "market_slug", "title",
        "outcome", "sector", "side", "role", "price", "shares", "timestamp",
        "tx_hash", "order_hash",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_markdown(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_smart_money_archive(value), encoding="utf-8")


def _notional(row: dict) -> float:
    return _float(row.get("price")) * _float(row.get("shares"))


def _float(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _unix_to_iso(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except Exception:
        return None
