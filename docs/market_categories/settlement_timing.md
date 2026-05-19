# Settlement Timing Playbook

This playbook covers wallets that enter late in a market lifecycle, especially
inside the final 24h or final 6h before resolution.

## Detection

- `is_last_24h` median at or above 20%, or `is_last_6h` median at or above 5%.
- Positive `settlement_window_edge` strengthens confidence.
- `exit_quality_proxy` helps distinguish tradable exits from hold-to-expiry
  behavior.

## Required Factors

- `time_to_resolution_secs`
- `resolution_lead_time_hours`
- `is_last_24h`
- `is_last_6h`
- `settlement_window_edge`
- `entry_forward_edge`
- `exit_quality_proxy`

## Validation Checklist

- Prefer settlement-audited PnL over fill-only proxies.
- Separate resolved markets from still-open positions.
- Penalize late alerts for realistic execution delay.
- Confirm the edge replicates outside the first discovered wallet.

## ReAct Loop

When this category appears, ReAct validates `settlement_window_edge`,
`is_last_6h`, and `exit_quality_proxy`.
