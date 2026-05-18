"""Factor lifecycle primitives.

Candidate factors should move through this lifecycle:
candidate -> researching -> validating -> approved/rejected -> live/decayed.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FactorCandidate:
    factor_id: str
    name: str
    lifecycle_state: str = "candidate"
    priority: int = 3
    required_data: str = "factor_table"
    owner_module: str | None = None
    hypothesis: str | None = None
    evidence: dict = field(default_factory=dict)


FACTOR_LIFECYCLE_STATES = (
    "candidate",
    "researching",
    "validating",
    "approved",
    "rejected",
    "live",
    "decayed",
)

__all__ = ["FACTOR_LIFECYCLE_STATES", "FactorCandidate"]
