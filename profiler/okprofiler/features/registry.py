from dataclasses import dataclass

import polars as pl

from .catalog import FACTOR_DEFINITIONS


@dataclass(frozen=True)
class FactorSpec:
    column: str
    label: str
    direction: str
    quantile: float
    live_feature: str | None = None
    requires: tuple[str, ...] = ()
    validation_role: str = "candidate"


FACTOR_SPECS = [
    FactorSpec(
        definition.column,
        definition.label,
        definition.direction,
        definition.quantile,
        definition.live_feature,
        definition.requires,
        definition.validation_role,
    )
    for definition in FACTOR_DEFINITIONS
]


def available_specs(df: pl.DataFrame) -> list[FactorSpec]:
    return [spec for spec in FACTOR_SPECS if spec.column in df.columns]
