# Feature Library

This directory is the executable factor library for the Python profiler. Keep
one coherent factor family per file; avoid growing `derived.py` into a large
miscellaneous module.

## Structure

```text
basic.py       generic fill/CLOB-derived factors such as notional and abs momentum
behavior.py    wallet behavior factors such as re-entry count and buy ratio
catalog.py     source-of-truth factor catalog: category, formula, dependencies
library.py     one FactorImplementation per factor; applies stages in order
clob.py        raw CLOB event feature extraction
timing.py      clock, news, and resolution-window factors
weather.py     weather-temperature market semantic factors
registry.py    executable validation/mining registry generated from catalog.py
derived.py     thin compatibility wrapper over library.py
```

## Factor Catalog

`catalog.py` is the first place to look when asking what a factor means. Each
entry records:

- output column,
- category/playbook,
- calculation formula in plain English,
- implementation function,
- data dependencies,
- live feature mapping when a Rust live signal can consume it.

The CLI can render this catalog:

```bash
python profiler/profile_wallets.py list-factors
python profiler/profile_wallets.py list-factors --category sector
python profiler/profile_wallets.py list-factors --category settlement_timing --json
```

`library.py` is the execution layer. It registers one `FactorImplementation`
per factor and groups implementations by stage so shared calculations are run
once:

```python
from okprofiler.features import add_factor

add_factor(
    "my_new_factor",
    compute=add_my_new_factor,
    stage="reverse_engineering",
    dependencies=("entry_forward_edge",),
)
```

The factor must already exist in `catalog.py`; otherwise `add_factor` raises an
error. This keeps the formula/category record and the executable implementation
aligned.

## Promotion Flow

1. Add or update one family module, for example `weather.py`.
2. Add one `FactorDefinition` in `catalog.py`.
3. Register one `FactorImplementation` in `library.py` with `add_factor`.
4. Document the factor in `docs/factors.md` when it is user-facing.
5. If it belongs to a market-specific process, update the matching playbook in
   `docs/market_categories/`.

Useful future families:

- `forecast.py`: weather forecast joins and forecast-error factors.
- `pnl.py`: market-category realized PnL and expectancy factors.
- `sector.py`: event/sector concentration factors.
- `execution.py`: exit quality, BBO distance, maker/taker behavior.
