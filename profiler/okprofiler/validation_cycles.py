import json
from collections import Counter
from pathlib import Path

import polars as pl

from .factor_library import FACTOR_SPECS, FactorSpec
from .validation import validate_factor


DEFAULT_CYCLES = [
    {"name": "baseline", "min_rows": 20, "min_oos_lift": 0.02, "min_stability": 0.35},
    {"name": "low_bar", "min_rows": 20, "min_oos_lift": 0.01, "min_stability": 0.25},
    {"name": "strict", "min_rows": 50, "min_oos_lift": 0.03, "min_stability": 0.45},
    {"name": "stability", "min_rows": 30, "min_oos_lift": 0.02, "min_stability": 0.60},
]


def run_validation_cycles(
    factor_table: pl.DataFrame,
    factors: list[str] | None = None,
    cycles: list[dict] | None = None,
) -> dict:
    cycles = cycles or DEFAULT_CYCLES
    specs = _selected_specs(factor_table, factors)
    results = []
    for spec in specs:
        validations = []
        for cycle in cycles:
            validation = validate_factor(
                factor_table,
                spec,
                min_rows=int(cycle["min_rows"]),
                min_oos_lift=float(cycle["min_oos_lift"]),
                min_stability=float(cycle["min_stability"]),
            )
            validations.append(
                {
                    "cycle": cycle["name"],
                    "min_rows": cycle["min_rows"],
                    "min_oos_lift": cycle["min_oos_lift"],
                    "min_stability": cycle["min_stability"],
                    "verdict": validation.get("verdict"),
                    "target": validation.get("target"),
                    "validation_role": validation.get("validation_role"),
                    "rows": validation.get("rows", 0),
                    "out_of_sample_score": validation.get("out_of_sample_score", 0.0),
                    "negative_control_score": validation.get("negative_control_score", 0.0),
                    "negative_set_score": validation.get("negative_set_score", 0.0),
                    "replication_score": validation.get("replication_score", 0.0),
                    "stability_score": validation.get("stability_score", 0.0),
                    "decay_score": validation.get("decay_score", 0.0),
                    "reason": validation.get("reason"),
                    "validation_id": validation.get("validation_id"),
                }
            )
        results.append(_summarize_factor(spec, validations))
    return {
        "version": 1,
        "cycle_count": len(cycles),
        "factor_count": len(results),
        "cycles": cycles,
        "factors": results,
        "summary": _summary(results),
    }


def write_validation_cycles(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def render_validation_cycles(result: dict) -> str:
    lines = [
        "# Factor Validation Cycles",
        "",
        f"- cycle_count: {result['cycle_count']}",
        f"- factor_count: {result['factor_count']}",
        "- summary: "
        + ", ".join(f"{key}={value}" for key, value in sorted(result.get("summary", {}).items())),
        "",
        "| Factor | Consensus | Confirmed | Cycles | Verdicts | Reason |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in result.get("factors", []):
        verdicts = ", ".join(f"{key}={value}" for key, value in sorted(row["verdict_counts"].items()))
        lines.append(
            f"| `{row['factor_id']}` | {row['consensus']} | {row['confirmed_cycles']} | "
            f"{row['total_cycles']} | {verdicts} | {row['reason']} |"
        )
    return "\n".join(lines) + "\n"


def _selected_specs(factor_table: pl.DataFrame, factors: list[str] | None) -> list[FactorSpec]:
    by_column = {spec.column: spec for spec in FACTOR_SPECS}
    if factors:
        return [
            by_column[factor]
            for factor in factors
            if factor in by_column and factor in factor_table.columns
        ]
    return [spec for spec in FACTOR_SPECS if spec.column in factor_table.columns]


def _summarize_factor(spec: FactorSpec, validations: list[dict]) -> dict:
    verdicts = Counter(validation.get("verdict", "unknown") for validation in validations)
    confirmed = verdicts.get("approved", 0) + verdicts.get("researching", 0)
    total = len(validations)
    consensus = _consensus(verdicts, total)
    return {
        "factor_id": spec.column,
        "label": spec.label,
        "direction": spec.direction,
        "confirmed_cycles": confirmed,
        "total_cycles": total,
        "confirmation_rate": 0.0 if total == 0 else confirmed / total,
        "consensus": consensus,
        "verdict_counts": dict(sorted(verdicts.items())),
        "reason": _reason(consensus, verdicts, total),
        "validations": validations,
    }


def _consensus(verdicts: Counter, total: int) -> str:
    if total == 0:
        return "no_cycles"
    approved = verdicts.get("approved", 0)
    promising = verdicts.get("researching", 0)
    rejected = verdicts.get("rejected", 0) + verdicts.get("decayed", 0)
    blocked = verdicts.get("insufficient_data", 0) + verdicts.get("blocked", 0)
    if approved >= max(2, total // 2 + 1):
        return "confirmed_effective"
    if approved + promising >= max(2, total // 2 + 1):
        return "confirmed_promising"
    if blocked == total:
        return "blocked"
    if rejected >= max(2, total // 2 + 1):
        return "confirmed_rejected"
    return "mixed"


def _reason(consensus: str, verdicts: Counter, total: int) -> str:
    if consensus == "confirmed_effective":
        return "approved in most validation cycles"
    if consensus == "confirmed_promising":
        return "approved/researching in most validation cycles; expand sample"
    if consensus == "blocked":
        return "all cycles lacked enough data or required inputs"
    if consensus == "confirmed_rejected":
        return "rejected or decayed in most validation cycles"
    return f"mixed cycle verdicts over {total} runs: {dict(sorted(verdicts.items()))}"


def _summary(results: list[dict]) -> dict:
    return dict(sorted(Counter(row["consensus"] for row in results).items()))


def load_factor_table(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"factor table not found: {path}")
    return pl.read_parquet(path)
