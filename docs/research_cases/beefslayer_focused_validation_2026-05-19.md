# Focused Validation: @beefslayer Four High-Probability Directions

Date: 2026-05-19

Wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`

Profile directory: `data/profiler_real_beefslayer`

## Data Collected

- Public wallet fills: 3020 rows
- Gamma market metadata: 200 rows
- Weather observations: 853 rows
- Weather forecast history: 41400 rows
- Weather event contexts: 550 rows
- Official weather observations: 50 rows
- CLOB events: header only, no usable historical CLOB rows
- News timeline: missing
- Settlement/redemption events: missing

Diagnostics are not fully ready because CLOB history and news timeline are
missing.

## Required Verdicts

| Direction | Factors Checked | Verdict | Evidence |
| --- | --- | --- | --- |
| CLOB pressure / microstructure | `microstructure_pressure_edge`, `microstructure_entry_edge` | rejected for current profile; data quality caveat | `validation-cycles`: both `confirmed_rejected` across 4 cycles. Diagnostics still marks `clob_features` missing, so this is not a reliable CLOB alpha claim. |
| News lead-time | `news_lead_entry_edge`, `news_recency_decay_edge` | blocked by missing data | `news.csv` is missing. Both factors have zero non-null rows. |
| Settlement timing | `settlement_window_edge`, `settlement_urgency_edge` | rejected | ReAct and `validation-cycles` reject both. `settlement_window_edge`: oos lift 0.0000. `settlement_urgency_edge`: oos lift 0.0000. |
| Official weather station edge | `official_station_basis`, `official_station_target_bucket_edge` | mixed negative/blocking | `official_station_basis` rejected. `official_station_target_bucket_edge` blocked by insufficient non-null rows. |

## Validation-Cycles Output

Focused cycle command:

```bash
python profiler/profile_wallets.py validation-cycles \
  --factor-table data/profiler_real_beefslayer/factor_table.parquet \
  --factor microstructure_pressure_edge,microstructure_entry_edge,news_lead_entry_edge,news_recency_decay_edge,settlement_window_edge,settlement_urgency_edge,official_station_target_bucket_edge,official_station_basis \
  --out data/profiler_real_beefslayer/focused_validation_cycles.json
```

Result:

- `microstructure_pressure_edge`: `confirmed_rejected`
- `microstructure_entry_edge`: `confirmed_rejected`
- `settlement_window_edge`: `confirmed_rejected`
- `settlement_urgency_edge`: `confirmed_rejected`
- `official_station_target_bucket_edge`: `blocked`
- `official_station_basis`: `confirmed_rejected`

`news_lead_entry_edge` and `news_recency_decay_edge` were not included in the
cycle output because the real factor table has no non-null news-derived rows.

## Overall Factor State

`summarize-validations` on this real profile:

- total: 65
- effective: 0
- promising: 17
- blocked: 3
- rejected: 35
- not_tested: 10

No factor is approved.

Promising does not mean usable. The most notable researching factors are
`bucket_distance_from_normal`, `event_motif_recurrence`, and
`lead_time_evidence`, but all still lack replication or settlement-grade proof.

## Decision

No usable alpha factor has been confirmed for the four requested directions.

Next work should not add more abstract factors. It should collect the missing
evidence:

- historical or live CLOB snapshots for the traded asset set,
- timestamped news/social timeline,
- settlement/redemption evidence,
- more complete official station observations,
- non-wallet negative sets for replication.
