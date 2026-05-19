# Event/News Information Edge Playbook

This playbook covers wallets that trade close to external information releases:
news, RSS timelines, social timelines, official announcements, or other event
feeds. The key question is whether the wallet enters after public information
but before Polymarket reprices.

## Detection

- `news_reaction_window` median at or above 20%, or median
  `news_recency_hours` within 12 hours.
- Positive `news_lead_entry_edge` strengthens confidence.
- `lead_time_evidence` and `entry_before_move_secs` are used to avoid pure
  timestamp coincidence.

## Required Factors

- `pre_news_lag_secs`
- `news_recency_hours`
- `news_reaction_window`
- `news_lead_entry_edge`
- `entry_before_move_secs`
- `lead_time_evidence`
- `event_motif_recurrence`

## Validation Checklist

- Use timestamp-clean feeds only; no revised article times.
- Compare against non-news windows from the same markets.
- Require out-of-sample lift and negative-control lift before promotion.
- Check whether the edge survives spread/slippage and delayed alert execution.

## ReAct Loop

When this category appears, ReAct validates `news_lead_entry_edge`,
`lead_time_evidence`, `entry_before_move_secs`, and `event_motif_recurrence`.
