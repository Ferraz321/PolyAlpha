# Strategy Hunt Reliability Validation

Validation date: 2026-05-21

## What Was Tested

The new strategy hunt loop was tested with a seeded Polymarket wallet that had
already produced confirmed factor candidates in the weather board:

- wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`
- command: `hunt-strategies --wallet ... --history-limit 500 --history-max-offset 3500 --max-rounds 1`
- context: existing markets, weather observations, forecast history, weather
  event context, official weather, and CLOB file path were supplied.

## Verified Output

```text
found_reliable_strategy: false
research_ready_count: 1
wallet_status: not_reliable
archive_status: research_ready
classification: whale_watchlist
history_rows: 3022
effective_factor_count: 7
live_follow_ready: false
wallet_worth_following: rejected
edge_after_follow: rejected
```

## Interpretation

This is the intended behavior. The wallet has real, confirmed factor evidence,
but it is not a reliable follow strategy yet. The own-repeat delayed-entry proxy
is negative after slippage, and no live/paper follow database was supplied, so
latency, depth, and closed paper-follow edge cannot be approved.

The loop therefore refuses to stop at "interesting factor" and only stops on a
strategy when all four reliability gates are approved:

- wallet is worth following
- latency is acceptable
- depth can absorb the intended copy size
- edge survives after the follow delay and costs

Until a `data/follow.sqlite` database contains enough `wallet_trade_events`,
`follow_signals`, and `paper_follow_fills`, `hunt-strategies` can archive
candidates but must not approve live reliability.
