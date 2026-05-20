import json
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from .follow_eval import evaluate_followability
from .smart_money import SmartMoneyScanConfig, scan_smart_money
from .strategy_hunt_render import render_strategy_hunt


@dataclass(frozen=True)
class StrategyHuntConfig:
    scan_config: SmartMoneyScanConfig
    out_dir: Path
    max_rounds: int = 1
    interval_secs: int = 0
    until_found: bool = False
    follow_db: Path | None = None
    min_effective_factors: int = 1
    min_proxy_trades: int = 30
    max_latency_secs: int = 30
    min_live_events: int = 20
    min_depth_pass_rate: float = 0.8
    min_paper_fills: int = 30


def run_strategy_hunt(config: StrategyHuntConfig) -> dict:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    rounds = []
    reliable = []
    round_index = 0
    while _should_continue(config, round_index, reliable):
        round_index += 1
        round_result = _run_round(config, round_index)
        rounds.append(round_result)
        reliable.extend(row for row in round_result["strategies"] if row["status"] == "reliable")
        _write_snapshot(config, rounds, reliable, running=True)
        if reliable:
            break
        if _should_continue(config, round_index, reliable) and config.interval_secs > 0:
            time.sleep(config.interval_secs)

    result = _result(config, rounds, reliable, running=False)
    _write_json(config.out_dir / "strategy_hunt.json", result)
    (config.out_dir / "strategy_hunt.md").write_text(render_strategy_hunt(result), encoding="utf-8")
    return result


def _run_round(config: StrategyHuntConfig, round_index: int) -> dict:
    round_dir = config.out_dir / f"round_{round_index:03d}"
    scan_dir = round_dir / "smart_money"
    scan_result = scan_smart_money(replace(config.scan_config, out_dir=scan_dir))
    strategies = [
        _evaluate_wallet(wallet, config)
        for wallet in scan_result.get("wallets", [])
    ]
    round_result = {
        "round": round_index,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scan_dir": str(scan_dir),
        "recent_trade_rows": scan_result.get("recent_trade_rows", 0),
        "candidate_count": scan_result.get("candidate_count", 0),
        "research_ready_count": scan_result.get("research_ready_count", 0),
        "strategies": strategies,
        "reliable_count": sum(1 for row in strategies if row["status"] == "reliable"),
    }
    _write_json(round_dir / "strategy_round.json", round_result)
    return round_result


def _evaluate_wallet(wallet: dict, config: StrategyHuntConfig) -> dict:
    profile_dir = Path(wallet["wallet_dir"])
    follow = evaluate_followability(
        profile_dir=profile_dir,
        wallet=wallet.get("account"),
        min_proxy_trades=config.min_proxy_trades,
        db=config.follow_db,
        max_latency_secs=config.max_latency_secs,
        min_live_events=config.min_live_events,
        min_depth_pass_rate=config.min_depth_pass_rate,
        min_paper_fills=config.min_paper_fills,
    )
    status, reasons = _strategy_status(wallet, follow, config)
    result = {
        "account": wallet.get("account"),
        "status": status,
        "reasons": reasons,
        "archive_status": wallet.get("archive_status"),
        "classification": wallet.get("classification"),
        "effective_factor_count": wallet.get("effective_factor_count", 0),
        "smart_money_score": wallet.get("smart_money_score", 0.0),
        "history_rows": wallet.get("history_rows", 0),
        "wallet_dir": str(profile_dir),
        "follow_verdicts": follow.get("verdicts", {}),
        "live_follow_ready": follow.get("live_follow_evidence", {}).get("ready", False),
        "live_follow_reason": follow.get("live_follow_evidence", {}).get("reason"),
    }
    _write_json(profile_dir / "strategy_reliability.json", result)
    return result


def _strategy_status(wallet: dict, follow: dict, config: StrategyHuntConfig) -> tuple[str, list[str]]:
    reasons = []
    effective_count = int(wallet.get("effective_factor_count") or 0)
    if wallet.get("archive_status") != "research_ready":
        reasons.append(f"archive_status={wallet.get('archive_status')}")
    if effective_count < config.min_effective_factors:
        reasons.append(f"effective_factors={effective_count} < {config.min_effective_factors}")

    verdicts = follow.get("verdicts", {})
    required = ["wallet_worth_following", "latency_acceptable", "depth_can_eat", "edge_after_follow"]
    rejected = [
        f"{key}: {row.get('reason')}"
        for key in required
        for row in [verdicts.get(key, {})]
        if row.get("verdict") == "rejected"
    ]
    blocked = [
        f"{key}: {row.get('reason')}"
        for key in required
        for row in [verdicts.get(key, {})]
        if row.get("verdict") != "approved"
    ]
    if rejected:
        return "not_reliable", reasons + rejected
    if reasons:
        return "not_reliable", reasons + blocked
    if not blocked:
        return "reliable", ["factor evidence, latency, depth, and paper/live edge are all approved"]
    return "candidate_needs_live_proof", blocked


def _should_continue(config: StrategyHuntConfig, round_index: int, reliable: list[dict]) -> bool:
    if reliable:
        return False
    if config.until_found:
        return config.max_rounds <= 0 or round_index < config.max_rounds
    return round_index < max(1, config.max_rounds)


def _write_snapshot(config: StrategyHuntConfig, rounds: list[dict], reliable: list[dict], running: bool) -> None:
    result = _result(config, rounds, reliable, running=running)
    _write_json(config.out_dir / "strategy_hunt.json", result)
    (config.out_dir / "strategy_hunt.md").write_text(render_strategy_hunt(result), encoding="utf-8")


def _result(config: StrategyHuntConfig, rounds: list[dict], reliable: list[dict], running: bool) -> dict:
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "running": running,
        "found_reliable_strategy": bool(reliable),
        "round_count": len(rounds),
        "reliable_strategies": reliable,
        "config": {
            "out_dir": str(config.out_dir),
            "max_rounds": config.max_rounds,
            "until_found": config.until_found,
            "follow_db": str(config.follow_db) if config.follow_db else None,
            "min_effective_factors": config.min_effective_factors,
            "min_live_events": config.min_live_events,
            "min_paper_fills": config.min_paper_fills,
        },
        "rounds": rounds,
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
