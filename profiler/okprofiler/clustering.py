import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


def cluster_wallets(factor_table: pl.DataFrame) -> list[dict]:
    if factor_table.is_empty() or "account" not in factor_table.columns:
        return []
    rows = []
    for account in sorted(factor_table.get_column("account").unique().to_list()):
        wallet = factor_table.filter(pl.col("account") == account)
        features = _wallet_features(wallet)
        label = _cluster_label(features)
        rows.append(
            {
                "cluster_id": f"behavior:{label}",
                "account": account,
                "method": "heuristic_v1",
                "label": label,
                "score": _confidence(features),
                "features": features,
            }
        )
    return rows


def write_clusters(clusters: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "clusters": clusters}, indent=2),
        encoding="utf-8",
    )


def persist_clusters(db: Path, clusters: list[dict]) -> int:
    if not clusters:
        return 0
    db.parent.mkdir(parents=True, exist_ok=True)
    schema = Path("sql/schema.sql")
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db) as conn:
        if schema.exists():
            conn.executescript(schema.read_text(encoding="utf-8"))
        for cluster in clusters:
            conn.execute(
                """
                INSERT INTO wallet_clusters (
                    cluster_id, account, method, label, score, features_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cluster_id, account) DO UPDATE SET
                    method = excluded.method,
                    label = excluded.label,
                    score = excluded.score,
                    features_json = excluded.features_json,
                    updated_at = excluded.updated_at
                """,
                (
                    cluster["cluster_id"],
                    cluster["account"],
                    cluster["method"],
                    cluster["label"],
                    str(cluster["score"]),
                    json.dumps(cluster["features"], sort_keys=True),
                    now,
                ),
            )
    return len(clusters)


def _wallet_features(wallet: pl.DataFrame) -> dict:
    trade_count = wallet.height
    buy_ratio = _ratio(wallet, "side", "buy")
    maker_ratio = _ratio(wallet, "role", "maker")
    avg_notional = _avg_notional(wallet)
    weather_ratio = _mean_or_zero(wallet, "is_weather_market")
    avg_spread = _mean_or_zero(wallet, "spread_filled")
    avg_ofi = _mean_or_zero(wallet, "ofi_filled")
    reentry = _mean_or_zero(wallet, "same_market_reentry_count")
    sector_concentration = _mean_or_zero(wallet, "sector_concentration")
    entry_edge = _mean_or_zero(wallet, "entry_forward_edge")
    exit_quality = _mean_or_zero(wallet, "exit_quality_proxy")
    repeat_motif = _mean_or_zero(wallet, "repeat_hour_motif_score")
    market_count = wallet.get_column("market_id").n_unique() if "market_id" in wallet.columns else 0
    return {
        "trade_count": trade_count,
        "market_count": market_count,
        "buy_ratio": buy_ratio,
        "maker_ratio": maker_ratio,
        "avg_notional": avg_notional,
        "weather_ratio": weather_ratio,
        "avg_spread": avg_spread,
        "avg_ofi": avg_ofi,
        "same_market_reentry": reentry,
        "sector_concentration": sector_concentration,
        "entry_edge": entry_edge,
        "exit_quality": exit_quality,
        "repeat_motif": repeat_motif,
    }


def _cluster_label(features: dict) -> str:
    if features["weather_ratio"] >= 0.60:
        return "weather_specialist"
    if features["maker_ratio"] >= 0.60 and features["trade_count"] >= 100:
        return "market_making_or_arb"
    if features["sector_concentration"] >= 0.60 and features["entry_edge"] > 0.0:
        return "sector_information_edge"
    if features["exit_quality"] > 0.0 and features["same_market_reentry"] >= 2.0:
        return "staged_entry_exit_trader"
    if features["repeat_motif"] >= 0.35 and features["trade_count"] >= 20:
        return "scheduled_motif_trader"
    if features["same_market_reentry"] >= 2.0:
        return "repeat_reentry_trader"
    if features["avg_notional"] >= 5000:
        return "large_ticket_directional"
    if features["market_count"] >= 20:
        return "broad_market_scanner"
    return "generalist"


def _confidence(features: dict) -> float:
    evidence = 0.0
    evidence += min(features["trade_count"] / 100.0, 1.0) * 0.35
    evidence += min(features["market_count"] / 20.0, 1.0) * 0.25
    evidence += max(features["weather_ratio"], features["maker_ratio"]) * 0.25
    evidence += min(abs(features["avg_ofi"]), 1.0) * 0.15
    evidence += min(features["sector_concentration"], 1.0) * 0.10
    evidence += min(abs(features["entry_edge"]) * 10.0, 1.0) * 0.10
    return round(min(evidence, 1.0), 4)


def _ratio(wallet: pl.DataFrame, column: str, value: str) -> float:
    if column not in wallet.columns or wallet.is_empty():
        return 0.0
    return wallet.filter(pl.col(column).cast(pl.Utf8).str.to_lowercase() == value).height / wallet.height


def _avg_notional(wallet: pl.DataFrame) -> float:
    if "price" not in wallet.columns or "shares" not in wallet.columns or wallet.is_empty():
        return 0.0
    value = wallet.select((pl.col("price") * pl.col("shares")).mean()).item()
    return 0.0 if value is None else float(value)


def _mean_or_zero(wallet: pl.DataFrame, column: str) -> float:
    if column not in wallet.columns or wallet.is_empty():
        return 0.0
    value = wallet.select(pl.col(column).cast(pl.Float64).mean()).item()
    return 0.0 if value is None else float(value)
