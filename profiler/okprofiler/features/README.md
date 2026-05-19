# Feature Library

This directory is the executable factor library for the Python profiler. Keep
one coherent factor family per file; avoid growing `derived.py` into a large
miscellaneous module.

## Structure

```text
basic.py       generic fill/CLOB-derived factors such as notional and abs momentum
behavior.py    wallet behavior factors such as re-entry count and buy ratio
catalog.py     source-of-truth factor catalog: category, formula, dependencies
clob.py        raw CLOB event feature extraction
timing.py      clock, news, and resolution-window factors
weather.py     weather-temperature market semantic factors
registry.py    executable factor registry generated from catalog.py
derived.py     orchestration only; calls each family module in order
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

## Promotion Flow

1. Add or update one family module, for example `weather.py`.
2. Wire the family into `derived.py` if it is a new module.
3. Add one `FactorDefinition` in `catalog.py`.
4. Document the factor in `docs/factors.md` when it is user-facing.
5. If it belongs to a market-specific process, update the matching playbook in
   `docs/market_categories/`.

Useful future families:

- `forecast.py`: weather forecast joins and forecast-error factors.
- `pnl.py`: market-category realized PnL and expectancy factors.
- `sector.py`: event/sector concentration factors.
- `execution.py`: exit quality, BBO distance, maker/taker behavior.
