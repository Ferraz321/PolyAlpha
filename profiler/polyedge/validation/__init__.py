"""Validation Lab primitives for anti-overfit research.

Validation outputs are intentionally separate from profiler rules. A profiler
rule explains observed wallet behavior; a validation result decides whether a
factor is reusable enough to become a strategy input.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorValidation:
    validation_id: str
    factor_id: str
    method: str
    verdict: str = "pending"
    in_sample_score: float | None = None
    out_of_sample_score: float | None = None
    negative_control_score: float | None = None
    stability_score: float | None = None
    slippage_bps: float | None = None
    capacity_usd: float | None = None
    report: dict = field(default_factory=dict)


VALIDATION_METHODS = (
    "walk_forward",
    "negative_control",
    "category_replication",
    "slippage_adjusted",
    "capacity",
    "decay_monitor",
)

__all__ = ["FactorValidation", "VALIDATION_METHODS"]
