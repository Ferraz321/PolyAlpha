use std::collections::{BTreeMap, HashMap, HashSet};

use anyhow::{Result, ensure};
use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;

use crate::model::{AccountMetrics, FillEvent, LiquidityRole, MarketClosedLoop, TradeSide};

#[derive(Debug, Clone, Copy)]
pub struct MetricsConfig {
    pub close_loop_alpha: Decimal,
}

impl Default for MetricsConfig {
    fn default() -> Self {
        Self {
            close_loop_alpha: dec!(0.95),
        }
    }
}

#[derive(Default)]
struct MarketAccumulator {
    buy_shares: Decimal,
    sell_shares: Decimal,
    buy_notional: Decimal,
    sell_notional: Decimal,
    first_trade_at: Option<DateTime<Utc>>,
    last_trade_at: Option<DateTime<Utc>>,
    sectors: HashSet<String>,
}

#[derive(Default)]
struct AccountAccumulator {
    total_volume: Decimal,
    trade_count: usize,
    maker_count: usize,
    markets: HashSet<String>,
    sector_counts: HashMap<String, usize>,
}

pub fn compute_account_metrics(
    fills: &[FillEvent],
    config: MetricsConfig,
) -> Result<(Vec<AccountMetrics>, Vec<MarketClosedLoop>)> {
    ensure!(
        config.close_loop_alpha > Decimal::ZERO && config.close_loop_alpha <= Decimal::ONE,
        "close_loop_alpha must be in (0, 1]"
    );

    let mut account_stats: HashMap<String, AccountAccumulator> = HashMap::new();
    let mut market_stats: BTreeMap<(String, String), MarketAccumulator> = BTreeMap::new();

    for fill in fills {
        ensure!(fill.price >= Decimal::ZERO, "price must be non-negative");
        ensure!(fill.shares > Decimal::ZERO, "shares must be positive");

        let notional = fill.price * fill.shares;
        let account = account_stats.entry(fill.account.clone()).or_default();
        account.total_volume += notional;
        account.trade_count += 1;
        account.markets.insert(fill.market_id.clone());
        if fill.role == LiquidityRole::Maker {
            account.maker_count += 1;
        }
        if let Some(sector) = fill.sector.as_deref().filter(|s| !s.is_empty()) {
            *account.sector_counts.entry(sector.to_string()).or_default() += 1;
        }

        let market = market_stats
            .entry((fill.account.clone(), fill.market_id.clone()))
            .or_default();
        match fill.side {
            TradeSide::Buy => {
                market.buy_shares += fill.shares;
                market.buy_notional += notional;
            }
            TradeSide::Sell => {
                market.sell_shares += fill.shares;
                market.sell_notional += notional;
            }
        }
        if let Some(sector) = fill.sector.as_deref().filter(|s| !s.is_empty()) {
            market.sectors.insert(sector.to_string());
        }
        market.first_trade_at = Some(match market.first_trade_at {
            Some(current) => current.min(fill.timestamp),
            None => fill.timestamp,
        });
        market.last_trade_at = Some(match market.last_trade_at {
            Some(current) => current.max(fill.timestamp),
            None => fill.timestamp,
        });
    }

    let closed_loops: Vec<MarketClosedLoop> = market_stats
        .into_iter()
        .filter_map(|((account, market_id), market)| {
            let is_closed = market.buy_shares > Decimal::ZERO
                && market.sell_shares >= config.close_loop_alpha * market.buy_shares;
            is_closed.then(|| MarketClosedLoop {
                account,
                market_id,
                buy_shares: market.buy_shares,
                sell_shares: market.sell_shares,
                buy_notional: market.buy_notional,
                sell_notional: market.sell_notional,
                pnl: market.sell_notional - market.buy_notional,
                first_trade_at: market.first_trade_at.expect("market has at least one fill"),
                last_trade_at: market.last_trade_at.expect("market has at least one fill"),
                sectors: market.sectors.into_iter().collect(),
            })
        })
        .collect();

    let closed_by_account = closed_loops.iter().fold(
        HashMap::<String, Vec<&MarketClosedLoop>>::new(),
        |mut acc, closed| {
            acc.entry(closed.account.clone()).or_default().push(closed);
            acc
        },
    );

    let mut metrics = account_stats
        .into_iter()
        .map(|(account, stats)| {
            let closed = closed_by_account.get(&account).cloned().unwrap_or_default();
            let total_pnl = closed.iter().map(|m| m.pnl).sum::<Decimal>();
            let wins: Vec<Decimal> = closed
                .iter()
                .filter_map(|m| (m.pnl > Decimal::ZERO).then_some(m.pnl))
                .collect();
            let losses: Vec<Decimal> = closed
                .iter()
                .filter_map(|m| (m.pnl < Decimal::ZERO).then_some(-m.pnl))
                .collect();
            let closed_count = closed.len();
            let win_rate = ratio(wins.len(), closed_count);
            let avg_win = average(&wins);
            let avg_loss = average(&losses);
            let profit_loss_ratio = if avg_loss > Decimal::ZERO {
                avg_win / avg_loss
            } else {
                Decimal::ZERO
            };
            let expectancy = win_rate * avg_win - (Decimal::ONE - win_rate) * avg_loss;
            let max_single_market_pnl_share = max_single_market_pnl_share(&closed, total_pnl);
            let avg_trade_size = if stats.trade_count > 0 {
                stats.total_volume / Decimal::from(stats.trade_count)
            } else {
                Decimal::ZERO
            };
            let maker_ratio = ratio(stats.maker_count, stats.trade_count);
            let (dominant_sector, sector_concentration) =
                dominant_sector(&stats.sector_counts, stats.trade_count);

            AccountMetrics {
                account,
                total_volume: stats.total_volume,
                avg_trade_size,
                trade_count: stats.trade_count,
                distinct_markets: stats.markets.len(),
                closed_markets: closed_count,
                total_pnl,
                win_rate,
                profit_loss_ratio,
                expectancy,
                max_single_market_pnl_share,
                maker_ratio,
                dominant_sector,
                sector_concentration,
            }
        })
        .collect::<Vec<_>>();

    metrics.sort_by(|a, b| b.total_pnl.cmp(&a.total_pnl));
    Ok((metrics, closed_loops))
}

fn average(values: &[Decimal]) -> Decimal {
    if values.is_empty() {
        Decimal::ZERO
    } else {
        values.iter().copied().sum::<Decimal>() / Decimal::from(values.len())
    }
}

fn ratio(numerator: usize, denominator: usize) -> Decimal {
    if denominator == 0 {
        return Decimal::ZERO;
    }

    let value = numerator as f64 / denominator as f64;
    Decimal::from_f64_retain(value).unwrap_or(Decimal::ZERO)
}

fn dominant_sector(
    counts: &HashMap<String, usize>,
    trade_count: usize,
) -> (Option<String>, Decimal) {
    let Some((sector, count)) = counts.iter().max_by_key(|(_, count)| *count) else {
        return (None, Decimal::ZERO);
    };

    (Some(sector.clone()), ratio(*count, trade_count))
}

fn max_single_market_pnl_share(closed: &[&MarketClosedLoop], total_pnl: Decimal) -> Decimal {
    if total_pnl <= Decimal::ZERO {
        return Decimal::ZERO;
    }

    closed
        .iter()
        .filter_map(|market| (market.pnl > Decimal::ZERO).then_some(market.pnl / total_pnl))
        .max()
        .unwrap_or(Decimal::ZERO)
}

#[cfg(test)]
mod tests {
    use chrono::TimeZone;

    use super::*;
    use crate::model::{FillEvent, LiquidityRole, TradeSide};

    #[test]
    fn computes_closed_loop_metrics() {
        let fills = vec![
            fill("0xabc", "m1", TradeSide::Buy, dec!(0.40), dec!(1000)),
            fill("0xabc", "m1", TradeSide::Sell, dec!(0.62), dec!(950)),
            fill("0xabc", "m2", TradeSide::Buy, dec!(0.70), dec!(1000)),
            fill("0xabc", "m2", TradeSide::Sell, dec!(0.20), dec!(1000)),
        ];

        let (metrics, closed) =
            compute_account_metrics(&fills, MetricsConfig::default()).expect("metrics");
        assert_eq!(closed.len(), 2);
        assert_eq!(metrics[0].closed_markets, 2);
        assert_eq!(metrics[0].win_rate.round_dp(2), dec!(0.50));
        assert_eq!(metrics[0].total_pnl, dec!(-311.00));
    }

    fn fill(
        account: &str,
        market_id: &str,
        side: TradeSide,
        price: Decimal,
        shares: Decimal,
    ) -> FillEvent {
        FillEvent {
            account: account.to_string(),
            market_id: market_id.to_string(),
            condition_id: None,
            event_slug: None,
            sector: Some("politics".to_string()),
            side,
            role: LiquidityRole::Taker,
            price,
            shares,
            timestamp: Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap(),
            tx_hash: None,
            order_hash: None,
        }
    }
}
