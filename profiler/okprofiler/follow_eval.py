import csv
import json
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median


def evaluate_followability(
    profile_dir: Path,
    wallet: str | None = None,
    delays: list[int] | None = None,
    horizon_secs: int = 3600,
    max_wait_secs: int = 300,
    slippage_bps: float = 50.0,
    min_proxy_trades: int = 30,
) -> dict:
    delays = delays or [5, 15, 60]
    fills = _read_fills(profile_dir / "fills.csv", wallet)
    clob_rows = _csv_data_rows(profile_dir / "clob_events.csv")
    diagnostics = _read_json(profile_dir / "diagnostics.json")
    validations = _read_validations(profile_dir / "factor_validations.json")
    focused_cycles = _read_json(profile_dir / "focused_validation_cycles.json")
    proxy = {
        str(delay): _own_repeat_proxy(
            fills,
            delay_secs=delay,
            horizon_secs=horizon_secs,
            max_wait_secs=max_wait_secs,
            slippage_bps=slippage_bps,
        )
        for delay in delays
    }
    verdicts = _verdicts(
        fills=fills,
        clob_rows=clob_rows,
        diagnostics=diagnostics,
        validations=validations,
        focused_cycles=focused_cycles,
        proxy=proxy,
        min_proxy_trades=min_proxy_trades,
    )
    return {
        "version": 1,
        "profile_dir": str(profile_dir),
        "wallet": wallet or _single_wallet(fills),
        "config": {
            "delays_secs": delays,
            "horizon_secs": horizon_secs,
            "max_wait_secs": max_wait_secs,
            "slippage_bps": slippage_bps,
            "min_proxy_trades": min_proxy_trades,
        },
        "data_readiness": {
            "fills": len(fills),
            "clob_events": clob_rows,
            "diagnostics_ready": diagnostics.get("ready", False),
            "missing_actions": diagnostics.get("missing_actions", []),
            "has_news": _source_ready(diagnostics, "news"),
            "has_clob_features": _source_ready(diagnostics, "clob_features"),
            "has_markets": _source_ready(diagnostics, "markets"),
            "has_settlement_events": False,
        },
        "verdicts": verdicts,
        "own_repeat_proxy": proxy,
        "follow_commands": _follow_commands(profile_dir),
    }


def render_followability(result: dict) -> str:
    lines = [
        "# Wallet Followability Report",
        "",
        f"- profile_dir: `{result['profile_dir']}`",
        f"- wallet: `{result.get('wallet')}`",
        "",
        "## Data Readiness",
        "",
    ]
    for key, value in result["data_readiness"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Verdicts",
            "",
            "| Question | Verdict | Reason |",
            "| --- | --- | --- |",
        ]
    )
    labels = {
        "wallet_worth_following": "某个钱包是否值得跟",
        "latency_acceptable": "跟单延迟是否可接受",
        "depth_can_eat": "盘口深度是否能吃",
        "edge_after_follow": "跟单后收益是否还在",
    }
    for key, label in labels.items():
        row = result["verdicts"][key]
        lines.append(f"| {label} | {row['verdict']} | {row['reason']} |")
    lines.extend(
        [
            "",
            "## Own-Repeat Proxy",
            "",
            "This proxy uses only the target wallet's later same-market fills. It is not market-wide paper following and cannot approve a live follow strategy by itself.",
            "",
            "| Delay | Samples | Win Rate | Avg Edge | Median Wait | Verdict Hint |",
            "| ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for delay, row in result["own_repeat_proxy"].items():
        lines.append(
            f"| {delay}s | {row['samples']} | {row['win_rate']:.2%} | "
            f"{row['avg_edge_after_cost']:.6f} | {row['median_wait_secs']}s | {row['verdict_hint']} |"
        )
    lines.extend(["", "## Next Commands", ""])
    for command in result["follow_commands"]:
        lines.append(f"- {command['reason']}: `{' '.join(command['command'])}`")
    return "\n".join(lines) + "\n"


def write_followability(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def _read_fills(path: Path, wallet: str | None) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if wallet and row.get("account", "").lower() != wallet.lower():
                continue
            timestamp = _parse_time(row.get("timestamp"))
            price = _to_float(row.get("price"))
            shares = _to_float(row.get("shares"))
            if timestamp is None or price is None or shares is None:
                continue
            rows.append(
                {
                    **row,
                    "timestamp_dt": timestamp,
                    "price_f": price,
                    "shares_f": shares,
                    "side_norm": row.get("side", "").lower(),
                }
            )
    return sorted(rows, key=lambda row: row["timestamp_dt"])


def _own_repeat_proxy(
    fills: list[dict],
    delay_secs: int,
    horizon_secs: int,
    max_wait_secs: int,
    slippage_bps: float,
) -> dict:
    by_market: dict[str, list[dict]] = {}
    for row in fills:
        by_market.setdefault(row["market_id"], []).append(row)
    samples = []
    slippage = slippage_bps / 10000.0
    for market_rows in by_market.values():
        times = [row["timestamp_dt"] for row in market_rows]
        for row in market_rows:
            if row["side_norm"] not in {"buy", "sell"}:
                continue
            target_time = row["timestamp_dt"] + timedelta(seconds=delay_secs)
            entry_index = bisect_left(times, target_time)
            if entry_index >= len(market_rows):
                continue
            entry = market_rows[entry_index]
            wait_secs = (entry["timestamp_dt"] - target_time).total_seconds()
            if wait_secs < 0 or wait_secs > max_wait_secs:
                continue
            exit_time = entry["timestamp_dt"] + timedelta(seconds=horizon_secs)
            exit_index = bisect_left(times, exit_time)
            if exit_index >= len(market_rows):
                continue
            exit_row = market_rows[exit_index]
            raw_edge = (
                exit_row["price_f"] - entry["price_f"]
                if row["side_norm"] == "buy"
                else entry["price_f"] - exit_row["price_f"]
            )
            edge_after_cost = raw_edge - abs(entry["price_f"]) * slippage
            samples.append(
                {
                    "edge_after_cost": edge_after_cost,
                    "wait_secs": wait_secs,
                    "notional": entry["price_f"] * min(row["shares_f"], entry["shares_f"]),
                }
            )
    if not samples:
        return {
            "samples": 0,
            "win_rate": 0.0,
            "avg_edge_after_cost": 0.0,
            "median_edge_after_cost": 0.0,
            "median_wait_secs": None,
            "verdict_hint": "blocked_no_proxy_samples",
        }
    edges = [row["edge_after_cost"] for row in samples]
    win_rate = sum(1 for edge in edges if edge > 0) / len(edges)
    avg_edge = mean(edges)
    return {
        "samples": len(samples),
        "win_rate": win_rate,
        "avg_edge_after_cost": avg_edge,
        "median_edge_after_cost": median(edges),
        "median_wait_secs": round(median(row["wait_secs"] for row in samples), 3),
        "median_notional": median(row["notional"] for row in samples),
        "verdict_hint": "positive_proxy" if avg_edge > 0 and win_rate >= 0.5 else "negative_proxy",
    }


def _verdicts(
    fills: list[dict],
    clob_rows: int,
    diagnostics: dict,
    validations: dict[str, dict],
    focused_cycles: dict,
    proxy: dict,
    min_proxy_trades: int,
) -> dict:
    best_proxy = _best_proxy(proxy)
    approved = [
        factor
        for factor, validation in validations.items()
        if validation.get("verdict") == "approved"
    ]
    focused_summary = {
        row.get("factor_id"): row.get("consensus")
        for row in focused_cycles.get("factors", [])
        if row.get("factor_id")
    }
    wallet_verdict = "blocked"
    wallet_reason = "no approved factors or live paper-follow record yet"
    if best_proxy and best_proxy["samples"] >= min_proxy_trades and best_proxy["avg_edge_after_cost"] <= 0:
        wallet_verdict = "rejected"
        wallet_reason = "own-repeat proxy is negative after delay/slippage and no approved factor offsets it"
    elif approved:
        wallet_reason = f"has approved factors {approved}, but still needs paper-follow execution proof"
    latency_reason = "no live wallet_trade_events with observed_at/received_at latency; historical Data API fills cannot measure reaction delay"
    depth_reason = "no historical CLOB book depth around wallet fills" if clob_rows == 0 else "CLOB rows exist; run depth/capacity paper-follow before live execution"
    depth_verdict = "blocked"
    if clob_rows > 0 and _source_ready(diagnostics, "clob_features"):
        depth_reason = "CLOB features available, but capacity model is not approved yet"
    edge_verdict = "blocked"
    edge_reason = "missing market-wide post-trade tape and settlement-audited follow PnL"
    if best_proxy and best_proxy["samples"] >= min_proxy_trades and best_proxy["avg_edge_after_cost"] <= 0:
        edge_verdict = "rejected"
        edge_reason = "own-repeat proxy shows non-positive edge after delay/slippage"
    return {
        "wallet_worth_following": {
            "verdict": wallet_verdict,
            "reason": wallet_reason,
            "approved_factors": approved,
            "focused_consensus": focused_summary,
        },
        "latency_acceptable": {
            "verdict": "blocked",
            "reason": latency_reason,
        },
        "depth_can_eat": {
            "verdict": depth_verdict,
            "reason": depth_reason,
        },
        "edge_after_follow": {
            "verdict": edge_verdict,
            "reason": edge_reason,
        },
    }


def _best_proxy(proxy: dict) -> dict | None:
    rows = [row for row in proxy.values() if row.get("samples", 0) > 0]
    if not rows:
        return None
    return max(rows, key=lambda row: (row["samples"], row["avg_edge_after_cost"]))


def _read_validations(path: Path) -> dict[str, dict]:
    data = _read_json(path)
    return {
        row["factor_id"]: row
        for row in data.get("validations", [])
        if row.get("factor_id")
    }


def _follow_commands(profile_dir: Path) -> list[dict]:
    return [
        {
            "reason": "start live wallet trade collection for latency measurement",
            "command": [
                "cargo",
                "run",
                "--",
                "collector-data-api",
                "--db",
                "data/follow.sqlite",
                "--interval-secs",
                "5",
            ],
        },
        {
            "reason": "collect live CLOB book snapshots for target assets",
            "command": [
                "cargo",
                "run",
                "--",
                "watch-clob",
                "--db",
                "data/follow.sqlite",
                "--assets-file",
                str(profile_dir / "clob_assets.txt"),
            ],
        },
        {
            "reason": "rerun followability after paper/live observation window",
            "command": [
                "python",
                "profiler/profile_wallets.py",
                "follow-evaluate",
                "--profile-dir",
                str(profile_dir),
            ],
        },
    ]


def _csv_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(newline="", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _source_ready(diagnostics: dict, source: str) -> bool:
    return diagnostics.get("sources", {}).get(source, {}).get("ready", False)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _single_wallet(fills: list[dict]) -> str | None:
    wallets = sorted({row.get("account") for row in fills if row.get("account")})
    return wallets[0] if len(wallets) == 1 else None


def _parse_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _to_float(raw) -> float | None:
    try:
        return None if raw in {None, ""} else float(raw)
    except (TypeError, ValueError):
        return None
