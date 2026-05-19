from datetime import datetime, timezone

import polars as pl

from .factor_library import FACTOR_SPECS, FactorSpec
from .validation import validate_factor


def run_factor_react_loop(
    factor_table: pl.DataFrame,
    rules: dict,
    diagnostics: dict,
    min_rows: int = 20,
) -> dict:
    discovered = _discover_factors(factor_table, rules, diagnostics)
    steps = []
    validations = []
    for spec, source in discovered:
        thought = _thought(spec, source)
        validation = validate_factor(factor_table, spec, min_rows=min_rows)
        action = _action(validation)
        steps.append(
            {
                "factor_id": spec.column,
                "source": source,
                "thought": thought,
                "action": "validate_factor",
                "observation": _observation(validation),
                "verdict": validation.get("verdict"),
                "next_action": action,
                "validation_id": validation.get("validation_id"),
            }
        )
        validations.append(validation)
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovered_count": len(discovered),
        "validated_count": len(validations),
        "steps": steps,
        "validations": validations,
        "summary": _summary(steps),
    }


def _discover_factors(
    factor_table: pl.DataFrame,
    rules: dict,
    diagnostics: dict,
) -> list[tuple[FactorSpec, str]]:
    specs = {spec.column: spec for spec in FACTOR_SPECS}
    discovered: dict[str, str] = {}
    for row in diagnostics.get("factor_coverage", []):
        if row.get("available") and row.get("factor") in specs:
            discovered[row["factor"]] = "diagnostics_available"
    for wallet in rules.get("wallets", []):
        mining = wallet.get("mining", {})
        for rule_name in ["best_rule", "best_live_rule"]:
            for condition in mining.get(rule_name, {}).get("conditions", []):
                column = condition.get("column")
                if column in specs:
                    discovered[column] = f"wallet_{rule_name}"
        for rule in mining.get("top_rules", []):
            for condition in rule.get("conditions", []):
                column = condition.get("column")
                if column in specs and column not in discovered:
                    discovered[column] = "wallet_top_rule"
        for category in wallet.get("market_categories", []):
            for factor in category.get("next_candidate_factors", []):
                if factor in specs and factor in factor_table.columns and factor not in discovered:
                    discovered[factor] = "market_category_candidate"
    return [(specs[factor], source) for factor, source in sorted(discovered.items())]


def _thought(spec: FactorSpec, source: str) -> str:
    return (
        f"Discovered `{spec.column}` from {source}; validate before lifecycle "
        "promotion or strategy use."
    )


def _observation(validation: dict) -> dict:
    return {
        "rows": validation.get("rows", 0),
        "threshold": validation.get("threshold"),
        "in_sample_score": validation.get("in_sample_score", 0.0),
        "out_of_sample_score": validation.get("out_of_sample_score", 0.0),
        "negative_control_score": validation.get("negative_control_score", 0.0),
        "negative_set_score": validation.get("negative_set_score", 0.0),
        "replication_score": validation.get("replication_score", 0.0),
        "stability_score": validation.get("stability_score", 0.0),
        "slippage_bps": validation.get("slippage_bps"),
        "capacity_usd": validation.get("capacity_usd"),
        "reason": validation.get("reason"),
    }


def _action(validation: dict) -> str:
    verdict = validation.get("verdict")
    if verdict == "approved":
        return "promote_candidate_or_enable_live_if_supported"
    if verdict == "researching":
        return "collect_more_data_and_revalidate"
    if verdict == "insufficient_data":
        return "collect_required_rows"
    if verdict == "decayed":
        return "mark_decayed_and_disable_strategy_use"
    return "reject_or_keep_as_diagnostic"


def _summary(steps: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for step in steps:
        verdict = step.get("verdict", "unknown")
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts
