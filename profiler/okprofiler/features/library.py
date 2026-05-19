from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Iterable

import polars as pl

from .basic import add_basic_factors
from .behavior import add_behavior_factors
from .catalog import FACTOR_DEFINITIONS, FACTOR_DEFINITIONS_BY_COLUMN, FactorDefinition
from .reverse_engineering import add_reverse_engineering_factors
from .timing import add_timing_factors
from .weather import add_weather_factors
from .weather_forecasts import add_weather_forecast_factors
from .weather_observations import add_weather_observation_factors


ComputeFn = Callable[[pl.DataFrame], pl.DataFrame]


@dataclass(frozen=True)
class FactorImplementation:
    definition: FactorDefinition
    compute: ComputeFn
    stage: str
    dependencies: tuple[str, ...] = ()

    @property
    def column(self) -> str:
        return self.definition.column

    def to_dict(self) -> dict:
        row = self.definition.to_dict()
        row["stage"] = self.stage
        row["dependencies"] = self.dependencies
        return row


class FactorLibrary:
    def __init__(self, stage_order: Iterable[str]):
        self.stage_order = tuple(stage_order)
        self._factors: OrderedDict[str, FactorImplementation] = OrderedDict()

    def add(self, implementation: FactorImplementation) -> FactorImplementation:
        column = implementation.column
        if column in self._factors:
            raise ValueError(f"duplicate factor implementation: {column}")
        if implementation.stage not in self.stage_order:
            raise ValueError(f"unknown factor stage for {column}: {implementation.stage}")
        self._factors[column] = implementation
        return implementation

    def add_factor(
        self,
        column: str,
        compute: ComputeFn,
        stage: str,
        dependencies: tuple[str, ...] = (),
    ) -> FactorImplementation:
        definition = FACTOR_DEFINITIONS_BY_COLUMN.get(column)
        if definition is None:
            raise KeyError(f"factor `{column}` must be added to catalog.py before implementation")
        return self.add(
            FactorImplementation(
                definition=definition,
                compute=compute,
                stage=stage,
                dependencies=dependencies,
            )
        )

    def compute(self, df: pl.DataFrame, columns: Iterable[str] | None = None) -> pl.DataFrame:
        target_columns = self._target_columns(columns)
        out = df
        for stage in self.stage_order:
            implementations = [
                implementation
                for implementation in self._factors.values()
                if implementation.stage == stage and implementation.column in target_columns
            ]
            if not implementations:
                continue
            out = implementations[0].compute(out)
        return out

    def implementation(self, column: str) -> FactorImplementation | None:
        return self._factors.get(column)

    def implementations(self) -> list[FactorImplementation]:
        return [
            self._factors[definition.column]
            for definition in FACTOR_DEFINITIONS
            if definition.column in self._factors
        ]

    def rows(self, category: str | None = None) -> list[dict]:
        return [
            implementation.to_dict()
            for implementation in self._factors.values()
            if _matches_category(implementation.definition, category)
        ]

    def _target_columns(self, columns: Iterable[str] | None) -> set[str]:
        if columns is None:
            return set(self._factors)
        target = set(columns)
        expanded = set(target)
        changed = True
        while changed:
            changed = False
            for column in list(expanded):
                implementation = self._factors.get(column)
                if implementation is None:
                    raise KeyError(f"unknown factor implementation: {column}")
                for dependency in implementation.dependencies:
                    if dependency not in expanded:
                        expanded.add(dependency)
                        changed = True
        return expanded


def identity(df: pl.DataFrame) -> pl.DataFrame:
    return df


FACTOR_LIBRARY = FactorLibrary(
    stage_order=[
        "pipeline",
        "basic",
        "timing",
        "behavior",
        "reverse_engineering",
        "weather",
        "weather_observations",
        "weather_forecasts",
    ]
)


def add_factor(
    column: str,
    compute: ComputeFn,
    stage: str,
    dependencies: tuple[str, ...] = (),
) -> FactorImplementation:
    return FACTOR_LIBRARY.add_factor(column, compute, stage, dependencies)


def add_factors(df: pl.DataFrame, columns: Iterable[str] | None = None) -> pl.DataFrame:
    return FACTOR_LIBRARY.compute(df, columns)


def factor_implementations() -> list[FactorImplementation]:
    return FACTOR_LIBRARY.implementations()


def factor_library_rows(category: str | None = None) -> list[dict]:
    return FACTOR_LIBRARY.rows(category)


def _matches_category(definition: FactorDefinition, category: str | None) -> bool:
    return (
        category is None
        or definition.category == category
        or category in definition.playbooks
    )


def _register_stage(columns: Iterable[str], compute: ComputeFn, stage: str) -> None:
    for column in columns:
        add_factor(column, compute, stage)


_register_stage(
    [
        "ofi_filled",
        "spread_filled",
        "depth_imbalance_filled",
        "price_momentum",
        "feature_lag_secs",
        "distance_to_bid",
        "distance_to_ask",
        "time_to_resolution_secs",
        "forecast_temp_f",
        "forecast_model_count",
    ],
    identity,
    "pipeline",
)
_register_stage(["trade_notional", "abs_price_momentum"], add_basic_factors, "basic")
_register_stage(
    [
        "pre_news_lag_secs",
        "entry_hour_utc",
        "nwp_node_lag_secs",
        "late_day_temperature_nowcast_edge",
        "is_last_24h",
        "is_last_6h",
    ],
    add_timing_factors,
    "timing",
)
_register_stage(["same_market_reentry_count", "buy_ratio"], add_behavior_factors, "behavior")
_register_stage(
    [
        "microstructure_entry_edge",
        "settlement_window_edge",
        "forward_price_move",
        "entry_forward_edge",
        "entry_before_move_secs",
        "lead_time_evidence",
        "entry_price_advantage",
        "exit_quality_proxy",
        "sector_concentration",
        "sector_trade_count",
        "sector_pnl_proxy",
        "sector_entry_edge",
        "sector_repeat_edge_score",
        "cross_sector_breadth",
        "resolution_lead_time_hours",
        "news_recency_hours",
        "news_reaction_window",
        "news_lead_entry_edge",
        "repeat_hour_motif_score",
        "repeat_entry_motif_count",
        "repeat_market_add_rate",
        "event_motif_recurrence",
    ],
    add_reverse_engineering_factors,
    "reverse_engineering",
)
_register_stage(
    [
        "is_weather_market",
        "weather_market_ratio",
        "weather_city_concentration",
        "weather_market_breadth",
        "weather_city_count",
        "temperature_mid_f",
        "temperature_bucket_width_f",
        "is_low_temp_bucket",
        "is_high_temp_bucket",
        "is_extreme_temperature_bucket",
        "weather_low_price_bucket_value",
        "official_station_source_available",
        "official_station_basis",
        "official_station_bucket_distance",
        "official_station_inside_bucket_now",
        "official_station_target_bucket_edge",
        "temperature_bucket_ladder_mispricing",
    ],
    add_weather_factors,
    "weather",
)
_register_stage(
    [
        "actual_temp_distance_to_bucket",
        "actual_temp_inside_bucket",
        "actual_temp_error_to_mid_f",
    ],
    add_weather_observation_factors,
    "weather_observations",
)
_register_stage(
    [
        "forecast_error_to_bucket",
        "forecast_inside_bucket",
        "forecast_delta_1h",
        "forecast_delta_6h",
        "forecast_volatility",
        "model_disagreement",
        "forecast_bias_error_f",
        "city_temperature_bias_edge",
        "bucket_distance_from_normal",
    ],
    add_weather_forecast_factors,
    "weather_forecasts",
)


IMPLEMENTED_COLUMNS = {implementation.column for implementation in FACTOR_LIBRARY.implementations()}
CATALOG_COLUMNS = {definition.column for definition in FACTOR_DEFINITIONS}
missing = CATALOG_COLUMNS - IMPLEMENTED_COLUMNS
extra = IMPLEMENTED_COLUMNS - CATALOG_COLUMNS
if missing or extra:
    raise RuntimeError(
        "factor implementation/catalog mismatch: "
        f"missing={sorted(missing)} extra={sorted(extra)}"
    )
