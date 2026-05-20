import json
import math
from collections import Counter
from pathlib import Path

import polars as pl

from .factor_library import FACTOR_SPECS, FactorSpec
from .features.catalog import FACTOR_DEFINITIONS_BY_COLUMN, FactorDefinition
from .statistics import numeric
from .validation import validate_factor
from .validation_cycles import DEFAULT_CYCLES


def discover_factors(
    factor_table: pl.DataFrame,
    category: str | None = None,
    max_base_factors: int = 24,
    max_interactions: int = 120,
) -> dict:
    if factor_table.is_empty():
        return _empty_result(category, "empty factor table")
    if "entry_forward_edge" not in factor_table.columns and "side" not in factor_table.columns:
        return _empty_result(category, "missing validation target")

    registered_specs = _registered_specs(factor_table, category)
    factor_table, synthetic_specs = _interaction_specs(
        factor_table,
        registered_specs,
        category=category,
        max_base_factors=max_base_factors,
        max_interactions=max_interactions,
    )
    results = []
    for spec, formula in [(spec, spec.column) for spec in registered_specs] + synthetic_specs:
        results.append(_summarize_spec(factor_table, spec, formula))

    results = sorted(results, key=_rank_key, reverse=True)
    return {
        "version": 1,
        "category": category,
        "rows": factor_table.height,
        "registered_candidates": len(registered_specs),
        "synthetic_candidates": len(synthetic_specs),
        "candidate_count": len(results),
        "summary": _summary(results),
        "confirmed_effective": [
            row for row in results if row["consensus"] == "confirmed_effective"
        ],
        "confirmed_promising": [
            row for row in results if row["consensus"] == "confirmed_promising"
        ],
        "rejected": [
            row for row in results if row["consensus"] == "confirmed_rejected"
        ][:25],
        "all_factors": results,
    }


def discover_factor_boards(
    factor_table: pl.DataFrame,
    categories: list[str | None],
    max_base_factors: int = 24,
    max_interactions: int = 120,
) -> dict:
    boards = [
        discover_factors(
            factor_table,
            category=category,
            max_base_factors=max_base_factors,
            max_interactions=max_interactions,
        )
        for category in categories
    ]
    return {
        "version": 1,
        "board_count": len(boards),
        "rows": factor_table.height,
        "summary": _board_summary(boards),
        "boards": boards,
    }


def write_factor_discovery(result: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(result), indent=2), encoding="utf-8")


def render_factor_discovery(result: dict, top: int = 20) -> str:
    if "boards" in result:
        return _render_board_discovery(result, top)
    summary = ", ".join(
        f"{key}={value}" for key, value in sorted(result.get("summary", {}).items())
    )
    lines = [
        "# Factor Discovery Report",
        "",
        f"- source_factor_table: {result.get('source_factor_table') or '-'}",
        f"- category: {result.get('category') or 'all'}",
        f"- rows: {result.get('rows', 0)}",
        f"- registered_candidates: {result.get('registered_candidates', 0)}",
        f"- synthetic_candidates: {result.get('synthetic_candidates', 0)}",
        f"- summary: {summary or '-'}",
        "",
    ]
    lines.extend(_render_section("Confirmed Effective", result.get("confirmed_effective", []), top))
    lines.extend(_render_section("Confirmed Promising", result.get("confirmed_promising", []), top))
    return "\n".join(lines) + "\n"


def _empty_result(category: str | None, reason: str) -> dict:
    return {
        "version": 1,
        "category": category,
        "rows": 0,
        "registered_candidates": 0,
        "synthetic_candidates": 0,
        "candidate_count": 0,
        "summary": {"blocked": 1},
        "reason": reason,
        "confirmed_effective": [],
        "confirmed_promising": [],
        "rejected": [],
        "all_factors": [],
    }


def _registered_specs(factor_table: pl.DataFrame, category: str | None) -> list[FactorSpec]:
    specs = []
    for spec in FACTOR_SPECS:
        definition = FACTOR_DEFINITIONS_BY_COLUMN.get(spec.column)
        if (
            definition is not None
            and spec.column in factor_table.columns
            and spec.validation_role == "candidate"
            and _matches_category(definition, category)
            and _is_numeric_candidate(factor_table, spec.column)
        ):
            specs.append(spec)
    if category is None or category == "marketbridge":
        specs.extend(_marketbridge_specs(factor_table))
    return specs


def _interaction_specs(
    factor_table: pl.DataFrame,
    base_specs: list[FactorSpec],
    category: str | None,
    max_base_factors: int,
    max_interactions: int,
) -> tuple[pl.DataFrame, list[tuple[FactorSpec, str]]]:
    bases = _ranked_base_specs(factor_table, base_specs, max_base_factors)
    if len(bases) < 2:
        return factor_table, []
    existing = set(factor_table.columns)
    out = []
    expressions = []
    for left_idx, left in enumerate(bases):
        for right in bases[left_idx + 1 :]:
            column = f"discovered__{left.column}__x__{right.column}"
            if column in existing:
                continue
            formula = f"{left.column} * {right.column}"
            expressions.append(
                (
                    pl.col(left.column).cast(pl.Float64).fill_null(0.0)
                    * pl.col(right.column).cast(pl.Float64).fill_null(0.0)
                ).alias(column)
            )
            label = f"{left.label} x {right.label}"
            out.append(
                (
                    FactorSpec(column, label, "high", 0.75, validation_role="candidate"),
                    formula,
                )
            )
            if len(out) >= max_interactions:
                break
        if len(out) >= max_interactions:
            break
    if not expressions:
        return factor_table, []
    enriched = factor_table.with_columns(expressions)
    return enriched, out


def _ranked_base_specs(
    factor_table: pl.DataFrame,
    specs: list[FactorSpec],
    max_base_factors: int,
) -> list[FactorSpec]:
    ranked = []
    for spec in specs:
        values = numeric(factor_table, spec.column)
        if len(values) < 20:
            continue
        unique = len(set(float(value) for value in values if math.isfinite(float(value))))
        if unique < 2:
            continue
        ranked.append((len(values), unique, spec))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [spec for _, _, spec in ranked[:max(0, max_base_factors)]]


def _summarize_spec(factor_table: pl.DataFrame, spec: FactorSpec, formula: str) -> dict:
    validations = []
    for cycle in DEFAULT_CYCLES:
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
                "verdict": validation.get("verdict"),
                "rows": validation.get("rows", 0),
                "threshold": _safe_float(validation.get("threshold")),
                "out_of_sample_score": _safe_float(validation.get("out_of_sample_score")),
                "negative_control_score": _safe_float(validation.get("negative_control_score")),
                "negative_set_score": _safe_float(validation.get("negative_set_score")),
                "replication_score": _safe_float(validation.get("replication_score")),
                "stability_score": _safe_float(validation.get("stability_score")),
                "decay_score": _safe_float(validation.get("decay_score")),
                "reason": validation.get("reason"),
            }
        )
    verdicts = Counter(validation["verdict"] for validation in validations)
    consensus = _consensus(verdicts, len(validations))
    definition = FACTOR_DEFINITIONS_BY_COLUMN.get(spec.column)
    return {
        "factor_id": spec.column,
        "label": spec.label,
        "category": definition.category if definition else "discovered",
        "playbooks": list(definition.playbooks) if definition else [],
        "direction": spec.direction,
        "quantile": spec.quantile,
        "formula": formula,
        "consensus": consensus,
        "confirmed_cycles": verdicts.get("approved", 0) + verdicts.get("researching", 0),
        "approved_cycles": verdicts.get("approved", 0),
        "total_cycles": len(validations),
        "verdict_counts": dict(sorted(verdicts.items())),
        "out_of_sample_score": _mean_metric(validations, "out_of_sample_score"),
        "replication_score": _mean_metric(validations, "replication_score"),
        "stability_score": _mean_metric(validations, "stability_score"),
        "validations": validations,
    }


def _matches_category(definition: FactorDefinition, category: str | None) -> bool:
    return (
        category is None
        or definition.category == category
        or category in definition.playbooks
    )


def _is_numeric_candidate(factor_table: pl.DataFrame, column: str) -> bool:
    values = numeric(factor_table, column)
    if len(values) == 0:
        return False
    finite = [float(value) for value in values if math.isfinite(float(value))]
    return len(finite) > 0 and len(set(finite)) > 1


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


def _summary(results: list[dict]) -> dict:
    return dict(sorted(Counter(row["consensus"] for row in results).items()))


def _board_summary(boards: list[dict]) -> dict:
    totals = Counter()
    for board in boards:
        for key, value in board.get("summary", {}).items():
            totals[key] += int(value)
    return dict(sorted(totals.items()))


def _marketbridge_specs(factor_table: pl.DataFrame) -> list[FactorSpec]:
    specs = []
    catalog_columns = {spec.column for spec in FACTOR_SPECS}
    for column in factor_table.columns:
        if not column.startswith("mb_") or column in catalog_columns:
            continue
        if _is_numeric_candidate(factor_table, column):
            specs.append(
                FactorSpec(
                    column=column,
                    label=column.replace("mb_", "MarketBridge ").replace("_", " "),
                    direction="high",
                    quantile=0.75,
                    validation_role="candidate",
                )
            )
    return specs


def _rank_key(row: dict) -> tuple:
    return (
        row["consensus"] == "confirmed_effective",
        row["approved_cycles"],
        row["confirmed_cycles"],
        row["out_of_sample_score"],
        row["replication_score"],
        row["stability_score"],
    )


def _mean_metric(validations: list[dict], key: str) -> float:
    values = [validation.get(key) for validation in validations]
    numeric_values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not numeric_values:
        return 0.0
    return sum(numeric_values) / len(numeric_values)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return value


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _render_section(title: str, rows: list[dict], top: int) -> list[str]:
    lines = [
        f"## {title}",
        "",
    ]
    if not rows:
        lines.extend(["No factors met this bar.", ""])
        return lines
    lines.extend(
        [
            "| Factor | Category | Approved | OOS | Replication | Stability | Formula |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows[:top]:
        lines.append(
            "| `{factor_id}` | {category} | {approved_cycles}/{total_cycles} | {oos:.4f} | "
            "{replication:.4f} | {stability:.4f} | {formula} |".format(
                factor_id=row["factor_id"],
                category=row["category"],
                approved_cycles=row["approved_cycles"],
                total_cycles=row["total_cycles"],
                oos=row["out_of_sample_score"],
                replication=row["replication_score"],
                stability=row["stability_score"],
                formula=_escape_table(row["formula"]),
            )
        )
    lines.append("")
    return lines


def _render_board_discovery(result: dict, top: int) -> str:
    summary = ", ".join(
        f"{key}={value}" for key, value in sorted(result.get("summary", {}).items())
    )
    lines = [
        "# Multi-Board Factor Discovery Report",
        "",
        f"- source_factor_table: {result.get('source_factor_table') or '-'}",
        f"- board_count: {result.get('board_count', 0)}",
        f"- rows: {result.get('rows', 0)}",
        f"- summary: {summary or '-'}",
        "",
        "| Board | Effective | Promising | Rejected | Top Effective Factor |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for board in result.get("boards", []):
        board_summary = board.get("summary", {})
        top_effective = "-"
        if board.get("confirmed_effective"):
            top_effective = f"`{board['confirmed_effective'][0]['factor_id']}`"
        lines.append(
            "| {category} | {effective} | {promising} | {rejected} | {top} |".format(
                category=board.get("category") or "all",
                effective=board_summary.get("confirmed_effective", 0),
                promising=board_summary.get("confirmed_promising", 0),
                rejected=board_summary.get("confirmed_rejected", 0),
                top=top_effective,
            )
        )
    lines.append("")
    for board in result.get("boards", []):
        lines.append(f"## Board: {board.get('category') or 'all'}")
        lines.append("")
        lines.extend(_render_section("Confirmed Effective", board.get("confirmed_effective", []), top))
    return "\n".join(lines) + "\n"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
