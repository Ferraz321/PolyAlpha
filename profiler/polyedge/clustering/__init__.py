"""Wallet clustering boundary.

Clustering groups wallets by behavior rather than identity: market category
mix, timing, trade sizing, PnL stability, maker/taker behavior, and factor
exposures.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WalletClusterAssignment:
    cluster_id: str
    account: str
    method: str
    label: str | None = None
    score: float | None = None
    features: dict = field(default_factory=dict)


__all__ = ["WalletClusterAssignment"]
