import csv
import json
import sqlite3
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
    db: Path | None = None,
    max_latency_secs: int = 30,
    min_live_events: int = 20,
    min_depth_pass_rate: float = 0.8,
    min_paper_fills: int = 30,
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
    live = _read_live_follow_evidence(
        db=db,
        wallet=wallet or _single_wallet(fills),
        max_latency_secs=max_latency_secs,
        min_live_events=min_live_events,
        min_depth_pass_rate=min_depth_pass_rate,
        min_paper_fills=min_paper_fills,
    )
    verdicts = _verdicts(
        fills=fills,
        clob_rows=clob_rows,
        diagnostics=diagnostics,
        validations=validations,
        focused_cycles=focused_cycles,
        proxy=proxy,
        min_proxy_trades=min_proxy_trades,
        live=live,
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
            "db": str(db) if db else None,
            "max_latency_secs": max_latency_secs,
            "min_live_events": min_live_events,
            "min_depth_pass_rate": min_depth_pass_rate,
            "min_paper_fills": min_paper_fills,
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
        "live_follow_evidence": live,
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
    live = result.get("live_follow_evidence", {})
    lines.extend(
        [
            "",
            "## Live/Paper Follow Evidence",
            "",
            f"- db: `{live.get('db')}`",
            f"- ready: {live.get('ready')}",
            f"- wallet_trade_events: {live.get('latency', {}).get('samples', 0)}",
            f"- latency_p50_secs: {live.get('latency', {}).get('p50_secs')}",
            f"- latency_p95_secs: {live.get('latency', {}).get('p95_secs')}",
            f"- depth_pass_rate: {live.get('depth', {}).get('pass_rate')}",
            f"- closed_paper_fills: {live.get('paper_edge', {}).get('closed_fills', 0)}",
            f"- avg_pnl: {live.get('paper_edge', {}).get('avg_pnl')}",
        ]
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
    live: dict | None = None,
) -> dict:
    live = live or {}
    live_verdicts = live.get("verdicts", {})
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
    live_wallet = live_verdicts.get("wallet_worth_following")
    if live_wallet and live_wallet["verdict"] != "blocked":
        wallet_verdict = live_wallet["verdict"]
        wallet_reason = live_wallet["reason"]
    elif best_proxy and best_proxy["samples"] >= min_proxy_trades and best_proxy["avg_edge_after_cost"] <= 0:
        wallet_verdict = "rejected"
        wallet_reason = "own-repeat proxy is negative after delay/slippage and no approved factor offsets it"
    elif live_wallet:
        wallet_verdict = live_wallet["verdict"]
        wallet_reason = live_wallet["reason"]
    elif approved:
        wallet_reason = f"has approved factors {approved}, but still needs paper-follow execution proof"
    latency_reason = "no live wallet_trade_events with observed_at/received_at latency; historical Data API fills cannot measure reaction delay"
    latency_verdict = "blocked"
    if live_verdicts.get("latency_acceptable"):
        latency_verdict = live_verdicts["latency_acceptable"]["verdict"]
        latency_reason = live_verdicts["latency_acceptable"]["reason"]
    depth_reason = "no historical CLOB book depth around wallet fills" if clob_rows == 0 else "CLOB rows exist; run depth/capacity paper-follow before live execution"
    depth_verdict = "blocked"
    if clob_rows > 0 and _source_ready(diagnostics, "clob_features"):
        depth_reason = "CLOB features available, but capacity model is not approved yet"
    if live_verdicts.get("depth_can_eat"):
        depth_verdict = live_verdicts["depth_can_eat"]["verdict"]
        depth_reason = live_verdicts["depth_can_eat"]["reason"]
    edge_verdict = "blocked"
    edge_reason = "missing market-wide post-trade tape and settlement-audited follow PnL"
    live_edge = live_verdicts.get("edge_after_follow")
    if live_edge and live_edge["verdict"] != "blocked":
        edge_verdict = live_edge["verdict"]
        edge_reason = live_edge["reason"]
    if (
        (not live_edge or live_edge["verdict"] != "approved")
        and best_proxy
        and best_proxy["samples"] >= min_proxy_trades
        and best_proxy["avg_edge_after_cost"] <= 0
    ):
        edge_verdict = "rejected"
        edge_reason = "own-repeat proxy shows non-positive edge after delay/slippage"
    elif live_edge:
        edge_verdict = live_edge["verdict"]
        edge_reason = live_edge["reason"]
    return {
        "wallet_worth_following": {
            "verdict": wallet_verdict,
            "reason": wallet_reason,
            "approved_factors": approved,
            "focused_consensus": focused_summary,
        },
        "latency_acceptable": {
            "verdict": latency_verdict,
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


def _read_live_follow_evidence(
    db: Path | None,
    wallet: str | None,
    max_latency_secs: int,
    min_live_events: int,
    min_depth_pass_rate: float,
    min_paper_fills: int,
) -> dict:
    result = {
        "db": str(db) if db else None,
        "ready": False,
        "reason": "no follow database supplied",
        "latency": {"samples": 0},
        "depth": {"signals": 0},
        "paper_edge": {"closed_fills": 0},
        "verdicts": {},
    }
    if not db:
        return result
    if not db.exists():
        result["reason"] = "follow database does not exist"
        return result
    account = wallet.lower() if wallet else None
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        required = ["wallet_trade_events", "follow_signals", "paper_follow_fills"]
        missing = [table for table in required if not _table_exists(conn, table)]
        if missing:
            result["reason"] = f"missing follow tables: {', '.join(missing)}"
            return result
        latency = _latency_evidence(conn, account, max_latency_secs)
        depth = _depth_evidence(conn, account)
        paper = _paper_edge_evidence(conn, account)
    verdicts = _live_verdicts(
        latency=latency,
        depth=depth,
        paper=paper,
        min_live_events=min_live_events,
        max_latency_secs=max_latency_secs,
        min_depth_pass_rate=min_depth_pass_rate,
        min_paper_fills=min_paper_fills,
    )
    return {
        **result,
        "ready": True,
        "reason": "loaded follow database",
        "latency": latency,
        "depth": depth,
        "paper_edge": paper,
        "verdicts": verdicts,
    }


def _latency_evidence(conn: sqlite3.Connection, account: str | None, max_latency_secs: int) -> dict:
    rows = _select_wallet_rows(
        conn,
        "SELECT latency_ms FROM wallet_trade_events {where}",
        account,
    )
    values = [max(0.0, row["latency_ms"] / 1000.0) for row in rows if row["latency_ms"] is not None]
    return {
        "samples": len(values),
        "p50_secs": _percentile(values, 0.50),
        "p95_secs": _percentile(values, 0.95),
        "max_latency_secs": max_latency_secs,
        "within_limit_rate": (
            sum(1 for value in values if value <= max_latency_secs) / len(values)
            if values
            else 0.0
        ),
    }


def _depth_evidence(conn: sqlite3.Connection, account: str | None) -> dict:
    rows = _select_wallet_rows(
        conn,
        "SELECT verdict, reasons_json FROM follow_signals {where}",
        account,
    )
    pass_count = sum(1 for row in rows if row["verdict"] == "paper")
    blocked_count = sum(1 for row in rows if row["verdict"] != "paper")
    missing_depth = 0
    for row in rows:
        try:
            reasons = json.loads(row["reasons_json"] or "[]")
        except json.JSONDecodeError:
            reasons = []
        if any("depth_status=missing" in reason for reason in reasons):
            missing_depth += 1
    total = pass_count + blocked_count
    return {
        "signals": total,
        "pass_count": pass_count,
        "blocked_count": blocked_count,
        "missing_depth_count": missing_depth,
        "pass_rate": pass_count / total if total else 0.0,
    }


def _paper_edge_evidence(conn: sqlite3.Connection, account: str | None) -> dict:
    where = "WHERE p.pnl IS NOT NULL"
    params: list[str] = []
    if account:
        where += " AND s.account = ?"
        params.append(account)
    rows = conn.execute(
        f"""
        SELECT CAST(p.pnl AS REAL) AS pnl, CAST(p.pnl_bps AS REAL) AS pnl_bps
        FROM paper_follow_fills p
        JOIN follow_signals s ON s.signal_id = p.signal_id
        {where}
        """,
        params,
    ).fetchall()
    pnls = [float(row["pnl"]) for row in rows if row["pnl"] is not None]
    pnl_bps = [float(row["pnl_bps"]) for row in rows if row["pnl_bps"] is not None]
    return {
        "closed_fills": len(pnls),
        "avg_pnl": mean(pnls) if pnls else None,
        "avg_pnl_bps": mean(pnl_bps) if pnl_bps else None,
        "win_rate": sum(1 for value in pnls if value > 0) / len(pnls) if pnls else 0.0,
    }


def _live_verdicts(
    latency: dict,
    depth: dict,
    paper: dict,
    min_live_events: int,
    max_latency_secs: int,
    min_depth_pass_rate: float,
    min_paper_fills: int,
) -> dict:
    latency_samples = latency.get("samples", 0)
    if latency_samples < min_live_events:
        latency_verdict = {
            "verdict": "blocked",
            "reason": f"only {latency_samples} live wallet events; need {min_live_events}",
        }
    elif (latency.get("p95_secs") or 0) <= max_latency_secs:
        latency_verdict = {
            "verdict": "approved",
            "reason": f"p95 latency {latency.get('p95_secs')}s <= {max_latency_secs}s",
        }
    else:
        latency_verdict = {
            "verdict": "rejected",
            "reason": f"p95 latency {latency.get('p95_secs')}s > {max_latency_secs}s",
        }

    signals = depth.get("signals", 0)
    pass_rate = depth.get("pass_rate", 0.0)
    if signals < min_live_events:
        depth_verdict = {
            "verdict": "blocked",
            "reason": f"only {signals} follow depth checks; need {min_live_events}",
        }
    elif depth.get("missing_depth_count", 0) == signals:
        depth_verdict = {
            "verdict": "blocked",
            "reason": "all follow checks are missing CLOB depth",
        }
    elif pass_rate >= min_depth_pass_rate:
        depth_verdict = {
            "verdict": "approved",
            "reason": f"depth pass rate {pass_rate:.2%} >= {min_depth_pass_rate:.2%}",
        }
    else:
        depth_verdict = {
            "verdict": "rejected",
            "reason": f"depth pass rate {pass_rate:.2%} < {min_depth_pass_rate:.2%}",
        }

    closed = paper.get("closed_fills", 0)
    avg_pnl = paper.get("avg_pnl")
    if closed < min_paper_fills:
        edge_verdict = {
            "verdict": "blocked",
            "reason": f"only {closed} closed paper-follow fills; need {min_paper_fills}",
        }
    elif avg_pnl is not None and avg_pnl > 0 and paper.get("win_rate", 0.0) >= 0.5:
        edge_verdict = {
            "verdict": "approved",
            "reason": f"paper-follow avg_pnl {avg_pnl:.6f}, win_rate {paper.get('win_rate'):.2%}",
        }
    else:
        edge_verdict = {
            "verdict": "rejected",
            "reason": f"paper-follow avg_pnl {avg_pnl}, win_rate {paper.get('win_rate'):.2%}",
        }

    components = [latency_verdict, depth_verdict, edge_verdict]
    if all(row["verdict"] == "approved" for row in components):
        wallet = {
            "verdict": "approved",
            "reason": "latency, depth, and closed paper-follow PnL are all approved",
        }
    elif any(row["verdict"] == "rejected" for row in components):
        wallet = {
            "verdict": "rejected",
            "reason": "at least one live followability component is rejected",
        }
    else:
        wallet = {
            "verdict": "blocked",
            "reason": "live follow evidence is still incomplete",
        }
    return {
        "wallet_worth_following": wallet,
        "latency_acceptable": latency_verdict,
        "depth_can_eat": depth_verdict,
        "edge_after_follow": edge_verdict,
    }


def _select_wallet_rows(conn: sqlite3.Connection, query_template: str, account: str | None):
    if account:
        return conn.execute(
            query_template.format(where="WHERE account = ?"),
            [account],
        ).fetchall()
    return conn.execute(query_template.format(where="")).fetchall()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        [table],
    ).fetchone()
    return row is not None


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 3)


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
            "reason": "record watchlist wallet events and paper-follow signals",
            "command": [
                "cargo",
                "run",
                "--",
                "follow-watch",
                "--db",
                "data/follow.sqlite",
                "--interval-secs",
                "5",
            ],
        },
        {
            "reason": "close mature paper-follow fills for edge-after-follow evidence",
            "command": [
                "cargo",
                "run",
                "--",
                "follow-close-paper",
                "--db",
                "data/follow.sqlite",
                "--horizon-secs",
                "3600",
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
                "--db",
                "data/follow.sqlite",
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
