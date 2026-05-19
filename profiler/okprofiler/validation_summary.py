import json
from collections import Counter
from pathlib import Path


EFFECTIVE_VERDICTS = {"approved"}
PROMISING_VERDICTS = {"researching"}
BLOCKED_VERDICTS = {"blocked", "insufficient_data"}
REJECTED_VERDICTS = {"rejected", "decayed"}


def summarize_validations(
    validations_path: Path | None = None,
    candidates_path: Path | None = None,
) -> dict:
    validations = _read_validations(validations_path)
    candidates = _read_candidates(candidates_path)
    rows = _merge_rows(validations, candidates)
    verdicts = Counter(row.get("verdict") or row.get("validation_status") or "not_tested" for row in rows)
    return {
        "version": 1,
        "source": {
            "validations": str(validations_path) if validations_path else None,
            "candidates": str(candidates_path) if candidates_path else None,
        },
        "total": len(rows),
        "effective": sum(1 for row in rows if _bucket(row) == "effective"),
        "promising": sum(1 for row in rows if _bucket(row) == "promising"),
        "blocked": sum(1 for row in rows if _bucket(row) == "blocked"),
        "rejected": sum(1 for row in rows if _bucket(row) == "rejected"),
        "not_tested": sum(1 for row in rows if _bucket(row) == "not_tested"),
        "verdict_counts": dict(sorted(verdicts.items())),
        "factors": rows,
    }


def render_summary(summary: dict) -> str:
    lines = [
        f"factor_effectiveness: total={summary['total']} "
        f"effective={summary['effective']} promising={summary['promising']} "
        f"blocked={summary['blocked']} rejected={summary['rejected']} "
        f"not_tested={summary['not_tested']}",
        "verdict_counts: "
        + ", ".join(f"{key}={value}" for key, value in summary["verdict_counts"].items()),
    ]
    for row in summary["factors"]:
        lines.append(
            f"- {row['factor_id']}: bucket={row['bucket']} "
            f"verdict={row.get('verdict') or row.get('validation_status') or 'not_tested'} "
            f"status={row.get('status', '-')}"
        )
    return "\n".join(lines) + "\n"


def _read_validations(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("validations", []) if isinstance(data, dict) else []


def _read_candidates(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("candidates", []) if isinstance(data, dict) else []


def _merge_rows(validations: list[dict], candidates: list[dict]) -> list[dict]:
    by_factor = {}
    for candidate in candidates:
        factor = candidate.get("factor") or candidate.get("factor_id")
        if factor:
            by_factor[factor] = {
                "factor_id": factor,
                "status": candidate.get("status"),
                "validation_status": candidate.get("validation_status"),
                "implementation_status": candidate.get("implementation_status"),
            }
    for validation in validations:
        factor = validation.get("factor_id")
        if not factor:
            continue
        existing = by_factor.get(factor, {"factor_id": factor})
        by_factor[factor] = {
            **existing,
            "verdict": validation.get("verdict"),
            "rows": validation.get("rows"),
            "out_of_sample_score": validation.get("out_of_sample_score"),
            "stability_score": validation.get("stability_score"),
            "reason": validation.get("reason"),
        }
    rows = []
    for row in by_factor.values():
        rows.append({**row, "bucket": _bucket(row)})
    return sorted(rows, key=lambda row: (row["bucket"], row["factor_id"]))


def _bucket(row: dict) -> str:
    verdict = row.get("verdict") or row.get("validation_status")
    if verdict in EFFECTIVE_VERDICTS:
        return "effective"
    if verdict in PROMISING_VERDICTS:
        return "promising"
    if verdict in BLOCKED_VERDICTS:
        return "blocked"
    if verdict in REJECTED_VERDICTS:
        return "rejected"
    return "not_tested"
