# Microstructure/Liquidity Timing Playbook

This playbook covers wallets whose entries line up with CLOB pressure: order
flow imbalance, depth imbalance, spread compression, and short-horizon price
momentum.

## Detection

- At least two CLOB-derived factors are present in the profile.
- `ofi_filled`, `depth_imbalance_filled`, or `price_momentum` show meaningful
  non-zero distributions.
- `microstructure_entry_edge` becomes the combined candidate factor.

## Required Factors

- `ofi_filled`
- `spread_filled`
- `depth_imbalance_filled`
- `price_momentum`
- `abs_price_momentum`
- `feature_lag_secs`
- `distance_to_bid`
- `distance_to_ask`
- `microstructure_entry_edge`

## Validation Checklist

- Validate using as-of CLOB snapshots only.
- Apply spread and slippage penalties.
- Estimate `strategy_capacity_usd` before live promotion.
- Confirm that edge is not just one illiquid market replay.

## ReAct Loop

When this category appears, ReAct validates `microstructure_entry_edge`,
`spread_filled`, `depth_imbalance_filled`, and `price_momentum`.
