# Followability: @beefslayer

Date: 2026-05-19

Wallet: `0x331bf91c132af9d921e1908ca0979363fc47193f`

Profile directory: `data/profiler_real_beefslayer`

## Question

Can this wallet be followed by a subscription/copy-trading bot?

The four required checks were:

- whether the wallet is worth following,
- whether follow latency is acceptable,
- whether visible depth can absorb the copied order,
- whether edge remains after the follower enters.

## Data

- Wallet fills: 3020
- Historical CLOB events around fills: 0
- News timeline: missing
- Settlement/redemption evidence: missing
- Gamma market metadata: ready
- Weather observations/forecast/event context: ready enough for weather research

## Verdicts

| Check | Verdict | Reason |
| --- | --- | --- |
| Wallet worth following | rejected | The historical own-repeat proxy is negative after delay/slippage and no approved factor offsets it. |
| Latency acceptable | blocked | There are no live wallet trade events with observed/received timestamps. Historical Data API fills cannot measure reaction delay. |
| Depth can eat | blocked | There is no historical CLOB book depth around the wallet fills. |
| Edge after follow | rejected | The own-repeat proxy shows non-positive edge after delay and slippage. |

## Own-Repeat Proxy

This proxy uses only the target wallet's later same-market fills. It is not a
market-wide tape and cannot approve live following. It can, however, reject weak
follow candidates when it is already negative.

| Delay | Samples | Win Rate | Avg Edge After Cost | Median Wait |
| ---: | ---: | ---: | ---: | ---: |
| 5s | 135 | 48.89% | -0.008360 | 29s |
| 15s | 105 | 46.67% | -0.017752 | 53s |
| 60s | 80 | 45.00% | -0.027507 | 76s |

## Decision

Do not enable live copy trading for this wallet.

The wallet can remain on a watchlist for data collection, but it should not be
copied until a live paper-follow window proves:

- observed wallet event latency,
- CLOB depth/capacity at the copied price,
- positive paper PnL after delay and slippage,
- and no dependence on unavailable settlement-grade labels.

## Next Commands

```bash
cargo run -- collector-data-api \
  --db data/follow.sqlite \
  --interval-secs 5

cargo run -- watch-clob \
  --db data/follow.sqlite \
  --assets-file data/profiler_real_beefslayer/clob_assets.txt

cargo run -- follow-watch \
  --db data/follow.sqlite \
  --interval-secs 5 \
  --max-latency-secs 30 \
  --copy-fraction 0.1 \
  --max-notional 100

cargo run -- follow-close-paper \
  --db data/follow.sqlite \
  --horizon-secs 3600

python profiler/profile_wallets.py follow-evaluate \
  --profile-dir data/profiler_real_beefslayer \
  --wallet 0x331bf91c132af9d921e1908ca0979363fc47193f \
  --db data/follow.sqlite
```
