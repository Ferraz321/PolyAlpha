import polars as pl

from .basic import add_basic_factors
from .behavior import add_behavior_factors
from .timing import add_timing_factors
from .weather import add_weather_factors


def add_derived_factors(df: pl.DataFrame) -> pl.DataFrame:
    out = add_basic_factors(df)
    out = add_timing_factors(out)
    out = add_behavior_factors(out)
    out = add_weather_factors(out)
    return out
