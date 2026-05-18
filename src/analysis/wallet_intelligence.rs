use std::collections::{HashMap, HashSet};

use anyhow::{Result, ensure};
use chrono::Utc;
use rust_decimal::Decimal;
use serde::Serialize;

use crate::model::{FillEvent, TradeSide};

#[derive(Debug, Clone, Serialize)]
pub struct PositionSnapshot {
    pub account: String,
    pub market_id: String,
    pub outcome_id: String,
    pub shares: Decimal,
    pub avg_price: Decimal,
    pub cost_basis: Decimal,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct WalletPnlSnapshot {
    pub account: String,
    pub scope: String,
    pub realized_pnl: Decimal,
    pub unrealized_pnl: Decimal,
    pub trade_count: usize,
    pub market_count: usize,
    pub audit_status: String,
    pub evidence_json: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct WalletIntelligenceSnapshot {
    pub positions: Vec<PositionSnapshot>,
    pub wallet_pnl: Vec<WalletPnlSnapshot>,
}

#[derive(Debug, Default)]
struct PositionLedger {
    shares: Decimal,
    cost_basis: Decimal,
    realized_pnl: Decimal,
}

#[derive(Debug, Default)]
struct WalletLedger {
    realized_pnl: Decimal,
    trade_count: usize,
    markets: HashSet<String>,
}

pub fn build_wallet_intelligence(fills: &[FillEvent]) -> Result<WalletIntelligenceSnapshot> {
    let mut sorted = fills.to_vec();
    sorted.sort_by(|a, b| {
        a.timestamp
            .cmp(&b.timestamp)
            .then_with(|| a.account.cmp(&b.account))
            .then_with(|| a.market_id.cmp(&b.market_id))
    });

    let mut positions = HashMap::<(String, String), PositionLedger>::new();
    let mut wallets = HashMap::<String, WalletLedger>::new();

    for fill in &sorted {
        ensure!(fill.shares > Decimal::ZERO, "shares must be positive");
        ensure!(fill.price >= Decimal::ZERO, "price must be non-negative");
        let notional = fill.price * fill.shares;
        let key = (fill.account.clone(), fill.market_id.clone());
        let position = positions.entry(key).or_default();
        match fill.side {
            TradeSide::Buy => {
                position.shares += fill.shares;
                position.cost_basis += notional;
            }
            TradeSide::Sell => {
                let released_cost = released_cost(position, fill.shares);
                position.realized_pnl += notional - released_cost;
                position.shares = (position.shares - fill.shares).max(Decimal::ZERO);
                position.cost_basis = (position.cost_basis - released_cost).max(Decimal::ZERO);
            }
        }

        let wallet = wallets.entry(fill.account.clone()).or_default();
        wallet.trade_count += 1;
        wallet.markets.insert(fill.market_id.clone());
    }

    let updated_at = Utc::now().to_rfc3339();
    let positions = positions
        .into_iter()
        .map(|((account, market_id), ledger)| PositionSnapshot {
            account,
            market_id,
            outcome_id: "unknown".to_string(),
            shares: ledger.shares,
            avg_price: if ledger.shares > Decimal::ZERO {
                ledger.cost_basis / ledger.shares
            } else {
                Decimal::ZERO
            },
            cost_basis: ledger.cost_basis,
            realized_pnl: ledger.realized_pnl,
            unrealized_pnl: Decimal::ZERO,
            updated_at: updated_at.clone(),
        })
        .collect::<Vec<_>>();

    for position in &positions {
        wallets
            .entry(position.account.clone())
            .or_default()
            .realized_pnl += position.realized_pnl;
    }

    let mut wallet_pnl = wallets
        .into_iter()
        .map(|(account, wallet)| WalletPnlSnapshot {
            account,
            scope: "estimated_from_fills".to_string(),
            realized_pnl: wallet.realized_pnl,
            unrealized_pnl: Decimal::ZERO,
            trade_count: wallet.trade_count,
            market_count: wallet.markets.len(),
            audit_status: "estimated_from_fills".to_string(),
            evidence_json: r#"{"source":"fills","settlement_events":false}"#.to_string(),
            updated_at: updated_at.clone(),
        })
        .collect::<Vec<_>>();

    wallet_pnl.sort_by(|a, b| b.realized_pnl.cmp(&a.realized_pnl));
    Ok(WalletIntelligenceSnapshot {
        positions,
        wallet_pnl,
    })
}

fn released_cost(position: &PositionLedger, sell_shares: Decimal) -> Decimal {
    if position.shares <= Decimal::ZERO || position.cost_basis <= Decimal::ZERO {
        return Decimal::ZERO;
    }
    if sell_shares >= position.shares {
        return position.cost_basis;
    }
    (position.cost_basis / position.shares) * sell_shares
}

#[cfg(test)]
mod tests {
    use chrono::TimeZone;
    use rust_decimal_macros::dec;

    use super::*;
    use crate::model::{FillEvent, LiquidityRole};

    #[test]
    fn estimates_positions_and_wallet_pnl_from_fills() {
        let fills = vec![
            fill(TradeSide::Buy, dec!(0.40), dec!(100)),
            fill(TradeSide::Sell, dec!(0.70), dec!(40)),
        ];

        let snapshot = build_wallet_intelligence(&fills).expect("snapshot");

        assert_eq!(snapshot.positions.len(), 1);
        assert_eq!(snapshot.positions[0].shares, dec!(60));
        assert_eq!(snapshot.positions[0].cost_basis, dec!(24.00));
        assert_eq!(snapshot.positions[0].realized_pnl, dec!(12.00));
        assert_eq!(snapshot.wallet_pnl[0].realized_pnl, dec!(12.00));
    }

    fn fill(side: TradeSide, price: Decimal, shares: Decimal) -> FillEvent {
        FillEvent {
            account: "0xabc".to_string(),
            market_id: "m1".to_string(),
            condition_id: None,
            event_slug: None,
            sector: None,
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
