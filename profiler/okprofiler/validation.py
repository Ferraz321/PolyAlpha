import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from .factor_library import FactorSpec, available_specs
from .statistics import numeric, quantile


def validate_factor_table(
    factor_table: pl.DataFrame,
    min_rows: int = 20,
    min_oos_lift: float = 0.02,
    min_stability: float = 0.35,
) -> list[dict]:
    if factor_table.is_empty() or "side" not in factor_table.columns:
        return []
    return [
        _validate_factor(factor_table, spec, min_rows, min_oos_lift, min_stability)
        for spec in available_specs(factor_table)
        if len(numeric(factor_table, spec.column)) > 0
    ]


def write_validations(validations: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "validations": validations}, indent=2),
        encoding="utf-8",
    )


def persist_validations(db: Path, validations: list[dict]) -> int:
    if not validations:
        return 0
    db.parent.mkdir(parents=True, exist_ok=True)
    schema = Path("sql/schema.sql")
    with sqlite3.connect(db) as conn:
        if schema.exists():
            conn.executescript(schema.read_text(encoding="utf-8"))
        for validation in validations:
            conn.execute(
                """
                INSERT INTO factor_validations (
                    validation_id, factor_id, method, sample_start, sample_end,
                    in_sample_score, out_of_sample_score, negative_control_score,
                    stability_score, slippage_bps, capacity_usd, verdict, report_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(validation_id) DO UPDATE SET
                    sample_start = excluded.sample_start,
                    sample_end = excluded.sample_end,
                    in_sample_score = excluded.in_sample_score,
                    out_of_sample_score = excluded.out_of_sample_score,
                    negative_control_score = excluded.negative_control_score,
                    stability_score = excluded.stability_score,
                    slippage_bps = excluded.slippage_bps,
                    capacity_usd = excluded.capacity_usd,
                    verdict = excluded.verdict,
                    report_json = excluded.report_json
                """,
                (
                    validation["validation_id"],
                    validation["factor_id"],
                    validation["method"],
                    validation.get("sample_start"),
                    validation.get("sample_end"),
                    _score(validation.get("in_sample_score")),
                    _score(validation.get("out_of_sample_score")),
                    _score(validation.get("negative_control_score")),
                    _score(validation.get("stability_score")),
                    _score(validation.get("slippage_bps")),
                    _score(validation.get("capacity_usd")),
                    validation["verdict"],
                    json.dumps(validation, sort_keys=True),
                ),
            )
    return len(validations)


def approved_live_features(validations: list[dict]) -> set[str]:
    return {
        validation["live_feature"]
        for validation in validations
        if validation.get("verdict") == "approved" and validation.get("live_feature")
    }


def _validate_factor(
    df: pl.DataFrame,
    spec: FactorSpec,
    min_rows: int,
    min_oos_lift: float,
    min_stability: float,
) -> dict:
    clean = _clean_factor_rows(df, spec.column)
    sample_start, sample_end = _sample_window(clean)
    if clean.height < min_rows:
        return _result(
            spec,
            clean,
            sample_start,
            sample_end,
            verdict="insufficient_data",
            reason=f"rows {clean.height} < {min_rows}",
        )

    train, test = _time_split(clean)
    threshold = _threshold(train, spec)
    in_sample = _precision_lift(train, spec, threshold)
    out_of_sample = _precision_lift(test, spec, threshold)
    negative = _negative_control_lift(test, spec, threshold)
    stability = _stability(train, test, spec)
    verdict = _verdict(out_of_sample, negative, stability, min_oos_lift, min_stability)
    return _result(
        spec,
        clean,
        sample_start,
        sample_end,
        verdict=verdict,
        threshold=threshold,
        in_sample_score=in_sample,
        out_of_sample_score=out_of_sample,
        negative_control_score=negative,
        stability_score=stability,
        reason=_reason(verdict, out_of_sample, negative, stability),
    )


def _clean_factor_rows(df: pl.DataFrame, column: str) -> pl.DataFrame:
    columns = [column, "side"]
    if "timestamp" in df.columns:
        columns.append("timestamp")
    return df.select(columns).drop_nulls([column, "side"]).sort(
        "timestamp" if "timestamp" in df.columns else column
    )


def _time_split(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    midpoint = max(1, df.height // 2)
    return df.head(midpoint), df.tail(df.height - midpoint)


def _threshold(df: pl.DataFrame, spec: FactorSpec) -> float:
    values = numeric(df, spec.column)
    if len(values) == 0:
        return 0.0
    unique = set(float(value) for value in values)
    if unique.issubset({0.0, 1.0}):
        return 0.5
    return quantile(values, spec.quantile)


def _precision_lift(df: pl.DataFrame, spec: FactorSpec, threshold: float) -> float:
    if df.is_empty():
        return 0.0
    hits = df.filter(_hit_expr(spec, threshold))
    if hits.is_empty():
        return 0.0
    base_rate = _buy_rate(df)
    hit_rate = _buy_rate(hits)
    return max(0.0, hit_rate - base_rate)


def _negative_control_lift(df: pl.DataFrame, spec: FactorSpec, threshold: float) -> float:
    if df.is_empty():
        return 0.0
    hits = df.filter(~_hit_expr(spec, threshold))
    if hits.is_empty():
        return 0.0
    return max(0.0, _buy_rate(hits) - _buy_rate(df))


def _hit_expr(spec: FactorSpec, threshold: float) -> pl.Expr:
    column = pl.col(spec.column).fill_null(0.0)
    if spec.direction == "high":
        return column >= threshold
    return column <= threshold


def _buy_rate(df: pl.DataFrame) -> float:
    if df.is_empty():
        return 0.0
    return (
        df.filter(pl.col("side").str.to_lowercase() == "buy").height / df.height
    )


def _stability(train: pl.DataFrame, test: pl.DataFrame, spec: FactorSpec) -> float:
    left = numeric(train, spec.column)
    right = numeric(test, spec.column)
    if len(left) == 0 or len(right) == 0:
        return 0.0
    left_q = quantile(left, spec.quantile)
    right_q = quantile(right, spec.quantile)
    denom = abs(left_q) + 1e-9
    drift = abs(left_q - right_q)
    return max(0.0, 1.0 - min(drift / denom, 1.0))


def _verdict(
    out_of_sample: float,
    negative: float,
    stability: float,
    min_oos_lift: float,
    min_stability: float,
) -> str:
    if out_of_sample >= min_oos_lift and stability >= min_stability and negative <= out_of_sample:
        return "approved"
    if out_of_sample > 0.0 and stability > 0.0:
        return "researching"
    return "rejected"


def _result(
    spec: FactorSpec,
    df: pl.DataFrame,
    sample_start: str | None,
    sample_end: str | None,
    verdict: str,
    reason: str,
    threshold: float | None = None,
    in_sample_score: float = 0.0,
    out_of_sample_score: float = 0.0,
    negative_control_score: float = 0.0,
    stability_score: float = 0.0,
) -> dict:
    return {
        "validation_id": f"{spec.column}:walk_forward:v1",
        "factor_id": spec.column,
        "label": spec.label,
        "live_feature": spec.live_feature,
        "method": "walk_forward_negative_control",
        "verdict": verdict,
        "reason": reason,
        "rows": df.height,
        "sample_start": sample_start,
        "sample_end": sample_end,
        "threshold": threshold,
        "in_sample_score": in_sample_score,
        "out_of_sample_score": out_of_sample_score,
        "negative_control_score": negative_control_score,
        "stability_score": stability_score,
        "slippage_bps": None,
        "capacity_usd": None,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }


def _sample_window(df: pl.DataFrame) -> tuple[str | None, str | None]:
    if "timestamp" not in df.columns or df.is_empty():
        return None, None
    timestamps = df.get_column("timestamp")
    return str(timestamps.min()), str(timestamps.max())


def _reason(verdict: str, out_of_sample: float, negative: float, stability: float) -> str:
    return (
        f"{verdict}: oos_lift={out_of_sample:.4f}, "
        f"negative_lift={negative:.4f}, stability={stability:.4f}"
    )


def _score(value) -> str | None:
    return None if value is None else str(value)
