# Sector Information Edge Playbook

This playbook covers wallets that concentrate activity in one market sector and
enter before favorable repricing. The goal is to separate real information edge
from simple sector preference.

## Detection

- `sector_concentration` median at or above 55%, or `sector_trade_count` median
  at or above 5.
- Positive `sector_entry_edge` or `sector_repeat_edge_score` strengthens
  confidence.
- `cross_sector_breadth` splits narrow specialists from broad scanners.

## Required Factors

- `sector_concentration`
- `sector_trade_count`
- `sector_pnl_proxy`
- `sector_entry_edge`
- `sector_repeat_edge_score`
- `cross_sector_breadth`
- `event_motif_recurrence`

## Validation Checklist

- Walk-forward validation must beat wallet-shuffled negative controls.
- Replication should hold across at least two sectors before the factor can be
  generalized.
- Sector PnL must be checked against settlement-audited PnL when available.
- Capacity should be estimated with CLOB depth before strategy promotion.

## ReAct Loop

When this category appears, ReAct should validate `sector_entry_edge`,
`sector_repeat_edge_score`, `cross_sector_breadth`, and
`event_motif_recurrence` before promoting any strategy rule.
