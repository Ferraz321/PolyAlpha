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
                "source_wallet": wallet["account"],
                "enabled": False,
                "trigger": {"all": conditions},
                "risk": {"mode": "alert_only", "max_notional_usd": 0},
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
