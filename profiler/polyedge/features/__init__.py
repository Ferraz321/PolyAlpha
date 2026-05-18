"""Feature adapters for raw data sources.

This layer turns trades, CLOB state, market metadata, weather, news, settlement,
and social inputs into normalized columns that can be written to factor tables.
"""

from okprofiler.features import add_derived_factors, extract_clob_features

__all__ = ["add_derived_factors", "extract_clob_features"]
