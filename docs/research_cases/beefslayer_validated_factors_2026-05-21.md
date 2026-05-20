# Beefslayer Validated Factors

Date: 2026-05-21

Profile directory: `data/profiler_real_beefslayer`

Validation command:

```bash
PYTHONPATH=profiler .venv/bin/python profiler/profile_wallets.py validation-cycles \
  --factor-table data/profiler_real_beefslayer/factor_table.parquet \
  --out data/profiler_real_beefslayer/factor_validation_cycles.json
```

## Validation Target

The profiler now validates alpha candidates against `directional_success`,
defined as `entry_forward_edge > 0`, instead of merely explaining whether the
wallet bought or sold.

Factors marked `target` or `diagnostic` are blocked from approval. This keeps
future-return labels and ex-post realized weather observations from being
promoted as live entry factors.

## Confirmed Effective Factors

| Factor | Consensus | Cycle verdicts | OOS lift | Replication | Stability |
| --- | --- | --- | ---: | ---: | ---: |
| `hour_motif_timing_edge` | confirmed_effective | approved=4 | 0.0351 | 0.667 | 0.994 |
| `temperature_motif_edge` | confirmed_effective | approved=3, researching=1 | 0.0285 | 0.667 | 0.740 |
| `prior_reentry_hour_motif_edge` | confirmed_effective | approved=3, researching=1 | 0.0234 | 0.417 | 0.884 |
| `prior_reentry_buy_bias_edge` | confirmed_effective | approved=3, researching=1 | 0.0220 | 0.500 | 0.872 |
| `is_high_temp_bucket` | confirmed_effective | approved=3, researching=1 | 0.0256 | 0.583 | 1.000 |

Overall cycle summary:

```text
blocked=36, confirmed_effective=5, confirmed_promising=8, confirmed_rejected=31
```

## Interpretation

The validated factors point to a weather-temperature specialist with repeatable
timing behavior:

- strong entries cluster in high-temperature buckets;
- forecast distance from the traded bucket remains useful context;
- repeated UTC-hour behavior is predictive only when computed causally from
  prior fills;
- same-market reentry is useful when combined with prior timing or buy-bias
  behavior, not as a full-sample descriptor.

## Caveats

This is one-wallet validation. The five factors pass walk-forward, negative
control, stability, and grouped replication checks on the current real profile,
but should be revalidated on additional wallets and live MarketBridge-aligned
CLOB snapshots before live capital use.
