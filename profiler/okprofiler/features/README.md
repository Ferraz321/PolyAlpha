# Feature Library

This directory is the registry area for reverse-engineering factors.

Current implemented factors live in `okprofiler/factor_library.py` and are
materialized into `factor_table.parquet` by the pipeline. Add new factor ideas
here first as short research notes, then promote them into `factor_library.py`
when the input columns are available.

Useful families:

- order-flow: OFI, signed trade bursts, depth imbalance
- price action: short momentum, absolute shocks, entry-before-move
- execution quality: distance to BBO, spread, lag to CLOB snapshot
- event timing: time to resolution, pre-news lead time, market phase
- behavior: ticket-size regime, repeated market breadth, exit quality
