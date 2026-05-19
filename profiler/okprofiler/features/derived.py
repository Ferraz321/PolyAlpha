import polars as pl

from .library import add_factors


def add_derived_factors(
    df: pl.DataFrame,
    columns: list[str] | tuple[str, ...] | set[str] | None = None,
) -> pl.DataFrame:
    return add_factors(df, columns)
