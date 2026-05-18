"""Strategy reverse-engineering boundary.

This layer converts wallet intelligence into reusable behavioral hypotheses:
market preference, entry/exit timing, price context, resolution horizon,
information linkage, and repeated motifs.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BehaviorProfile:
    account: str
    market_categories: list[str] = field(default_factory=list)
    entry_logic: dict = field(default_factory=dict)
    exit_logic: dict = field(default_factory=dict)
    timing_profile: dict = field(default_factory=dict)
    caveats: list[str] = field(default_factory=list)


__all__ = ["BehaviorProfile"]
