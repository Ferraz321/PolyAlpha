import json


def strategy_config_from_rules(
    rules: dict,
    approved_features: set[str] | None = None,
) -> str:
    strategies = []
    for wallet in rules.get("wallets", []):
        if wallet.get("status") == "small_sample":
            continue
        conditions = _live_conditions(wallet.get("mining", {}).get("best_live_rule", {}))
        if not conditions:
            continue
        if approved_features is not None and not all(
            condition["feature"] in approved_features for condition in conditions
        ):
            continue
        strategies.append(
            {
                "id": f"reverse_{wallet['account'][:10]}",
                "version": 1,
                "source_wallet": wallet["account"],
                "enabled": False,
                "disabled_reason": "human_review_required",
                "score": _strategy_score(wallet),
                "trigger": {"all": conditions},
                "risk": _risk_limits(wallet),
                "position_sizing": _position_sizing(wallet),
            }
        )
    return json.dumps({"version": 1, "strategies": strategies}, indent=2)


def _live_conditions(rule: dict) -> list[dict]:
    out = []
    for condition in rule.get("conditions", []):
        feature = condition.get("feature")
        if feature is None:
            continue
        out.append(
            {
                "feature": feature,
                "op": condition["op"],
                "value": condition["value"],
            }
        )
    return out


def _strategy_score(wallet: dict) -> float:
    backtest = wallet.get("backtest", {})
    raw = (
        float(wallet.get("explainability_score", 0.0)) * 0.40
        + float(backtest.get("reproducibility_score", 0.0)) * 0.30
        + float(backtest.get("precision_proxy", 0.0)) * 0.20
        + float(backtest.get("factor_stability", 0.0)) * 0.10
    )
    return round(min(max(raw, 0.0), 1.0), 4)


def _risk_limits(wallet: dict) -> dict:
    score = _strategy_score(wallet)
    samples = int(wallet.get("samples", 0))
    max_notional = 0 if score < 0.80 else min(250.0, samples * 2.5)
    return {
        "mode": "alert_only",
        "max_notional_usd": round(max_notional, 2),
        "max_position_usd": round(max_notional, 2),
        "max_daily_signals": 5 if samples >= 50 else 2,
        "max_market_exposure_usd": round(max_notional, 2),
        "stop_loss_bps": 2500,
        "cooldown_secs": 900,
    }


def _position_sizing(wallet: dict) -> dict:
    score = _strategy_score(wallet)
    return {
        "method": "score_scaled_fixed_fraction",
        "base_notional_usd": 0,
        "score": score,
        "scale": round(score, 4),
        "enabled_for_execution": False,
    }
