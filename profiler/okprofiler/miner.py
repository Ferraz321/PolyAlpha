import itertools

import polars as pl

from .factor_library import FactorSpec, available_specs
from .statistics import numeric, quantile, spike_zscore


def mine_wallet(
    wallet: pl.DataFrame,
    max_rules: int = 10,
    disabled_factors: set[str] | None = None,
) -> dict:
    disabled_factors = disabled_factors or set()
    specs = [
        spec
        for spec in available_specs(wallet)
        if spec.column not in disabled_factors and len(numeric(wallet, spec.column)) > 0
    ]
    singles = [_score_rule(wallet, [spec]) for spec in specs]
    pairs = [_score_rule(wallet, list(pair)) for pair in itertools.combinations(specs, 2)]
    rules = [rule for rule in singles + pairs if rule["hits"] > 0]
    rules.sort(key=lambda row: row["score"], reverse=True)
    live_rules = [rule for rule in rules if _is_live_rule(rule)]
    return {
        "factor_count": len(specs),
        "top_rules": rules[:max_rules],
        "best_rule": rules[0] if rules else _empty_rule(),
        "best_live_rule": live_rules[0] if live_rules else _empty_rule(),
    }


def _score_rule(wallet: pl.DataFrame, specs: list[FactorSpec]) -> dict:
    conditions = [_condition(wallet, spec) for spec in specs]
    expr = None
    for condition in conditions:
        clause = _expr(condition)
        expr = clause if expr is None else expr & clause
    predicted = wallet.with_columns(expr.alias("factor_hit"))
    hits = predicted.filter(pl.col("factor_hit"))
    buy_hits = hits.filter(pl.col("side").str.to_lowercase() == "buy").height
    buy_total = wallet.filter(pl.col("side").str.to_lowercase() == "buy").height
    coverage = hits.height / wallet.height if wallet.height else 0.0
    precision = buy_hits / hits.height if hits.height else 0.0
    recall = buy_hits / buy_total if buy_total else 0.0
    stability = _stability(wallet, specs)
    score = (coverage * 0.25) + (precision * 0.25) + (recall * 0.25) + (stability * 0.25)
    return {
        "name": " + ".join(spec.label for spec in specs),
        "conditions": conditions,
        "samples": wallet.height,
        "hits": hits.height,
        "coverage": coverage,
        "precision_proxy": precision,
        "recall_proxy": recall,
        "factor_stability": stability,
        "score": score,
    }


def _condition(wallet: pl.DataFrame, spec: FactorSpec) -> dict:
    values = numeric(wallet, spec.column)
    threshold = quantile(values, spec.quantile)
    op = ">=" if spec.direction == "high" else "<="
    return {
        "column": spec.column,
        "feature": spec.live_feature,
        "label": spec.label,
        "op": op,
        "value": threshold,
        "direction": spec.direction,
        "spike_zscore": spike_zscore(values),
    }


def _expr(condition: dict) -> pl.Expr:
    column = pl.col(condition["column"]).fill_null(0.0)
    if condition["op"] == ">=":
        return column >= condition["value"]
    return column <= condition["value"]


def _stability(wallet: pl.DataFrame, specs: list[FactorSpec]) -> float:
    if wallet.height < 4:
        return 0.0
    halves = wallet.sort("timestamp").with_row_index("row_nr")
    midpoint = wallet.height // 2
    left = halves.filter(pl.col("row_nr") < midpoint)
    right = halves.filter(pl.col("row_nr") >= midpoint)
    scores = []
    for spec in specs:
        left_values = numeric(left, spec.column)
        right_values = numeric(right, spec.column)
        denom = abs(quantile(left_values, spec.quantile)) + 1e-9
        drift = abs(quantile(left_values, spec.quantile) - quantile(right_values, spec.quantile))
        scores.append(max(0.0, 1.0 - min(drift / denom, 1.0)))
    return float(sum(scores) / len(scores)) if scores else 0.0


def _empty_rule() -> dict:
    return {
        "name": "no reproducible factor rule",
        "conditions": [],
        "samples": 0,
        "hits": 0,
        "coverage": 0.0,
        "precision_proxy": 0.0,
        "recall_proxy": 0.0,
        "factor_stability": 0.0,
        "score": 0.0,
    }


def _is_live_rule(rule: dict) -> bool:
    return all(condition.get("feature") is not None for condition in rule.get("conditions", []))
