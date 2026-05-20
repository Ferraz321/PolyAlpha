# Smart Money Archive Validation

Validation date: 2026-05-21

## What Was Tested

The new smart-money archive loop was tested against the public Polymarket Data
API in two modes:

1. Recent whale scan smoke test:
   - command: `scan-smart-money --page-size 100 --max-offset 0 --max-wallets 3 --min-trade-notional 1000 --history-limit 100 --history-max-offset 0 --no-profile`
   - result: fetched 100 recent trade rows, found 1 large-trade wallet candidate, fetched wallet history, and wrote archive files.
   - important behavior: the wallet was classified as `one_shot_whale` and was not promoted to research-ready.

2. Seeded smart-wallet reverse-engineering test:
   - wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`
   - command: `scan-smart-money --wallet ... --history-limit 500 --history-max-offset 3500` with existing markets, CLOB, weather, forecast, weather-event, and official-weather context.
   - result: fetched 3022 wallet history rows, built a profile, ran multi-board factor discovery, and archived the wallet as `research_ready`.

## Verified Output

```text
recent_trade_rows: 10
candidate_count: 1
archived_wallet_count: 1
research_ready_count: 1
wallet: 0x331bf91c132af9d921e1908ca0979363fc47193f
classification: whale_watchlist
history_rows: 3022
closed_markets: 224
rough_closed_loop_pnl: 8433.92
win_rate: 71.43%
effective_factor_count: 7
archive_status: research_ready
```

## Interpretation

The scanner can now separate recent one-shot whales from wallets worth deeper
research. A wallet becomes `research_ready` only when it has enough history,
the profiler runs successfully, and multi-board discovery finds confirmed
effective factors. This is intentionally not a live-trading approval; live use
still requires followability, latency, liquidity, and paper-fill checks.
