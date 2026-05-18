use std::collections::{HashMap, HashSet};

use anyhow::{Result, ensure};
use chrono::Utc;
use rust_decimal::Decimal;
use serde::Serialize;

use crate::model::{FillEvent, TradeSide};

#[derive(Debug, Clone, Default)]
pub struct WalletIntelligenceContext {
    pub token_metadata: HashMap<String, TokenMetadata>,
    pub mark_prices: HashMap<String, Decimal>,
    pub settlement_events: Vec<SettlementEvent>,
}

#[derive(Debug, Clone)]
pub struct TokenMetadata {
    pub market_id: String,
    pub outcome_id: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct SettlementEvent {
    pub event_id: String,
    pub account: String,
    pub market_id: String,
    pub outcome_id: Option<String>,
    pub event_type: String,
    pub amount: Decimal,
    pub payout: Decimal,
    pub settlement_price: Option<Decimal>,
    pub timestamp: String,
}

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
    build_wallet_intelligence_with_context(fills, &WalletIntelligenceContext::default())
}

pub fn build_wallet_intelligence_with_context(
    fills: &[FillEvent],
    context: &WalletIntelligenceContext,
) -> Result<WalletIntelligenceSnapshot> {
    let mut sorted = fills.to_vec();
    sorted.sort_by(|a, b| {
        a.timestamp
            .cmp(&b.timestamp)
            .then_with(|| a.account.cmp(&b.account))
            .then_with(|| a.market_id.cmp(&b.market_id))
    });

    let mut positions = HashMap::<(String, String, String), PositionLedger>::new();
    let mut wallets = HashMap::<String, WalletLedger>::new();

    for fill in &sorted {
        ensure!(fill.shares > Decimal::ZERO, "shares must be positive");
        ensure!(fill.price >= Decimal::ZERO, "price must be non-negative");
        let notional = fill.price * fill.shares;
        let token = context.token_metadata.get(&fill.market_id);
        let position_market_id = token
            .map(|metadata| metadata.market_id.clone())
            .unwrap_or_else(|| fill.market_id.clone());
        let outcome_id = token
            .map(|metadata| metadata.outcome_id.clone())
            .unwrap_or_else(|| fill.market_id.clone());
        let key = (fill.account.clone(), position_market_id.clone(), outcome_id);
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
        wallet.markets.insert(position_market_id);
    }

    let updated_at = Utc::now().to_rfc3339();
    let positions = positions
        .into_iter()
        .map(|((account, market_id, outcome_id), ledger)| {
            let avg_price = if ledger.shares > Decimal::ZERO {
                ledger.cost_basis / ledger.shares
            } else {
                Decimal::ZERO
            };
            let mark_price = context.mark_prices.get(&outcome_id).copied();
            let unrealized_pnl = mark_price
                .map(|price| (price - avg_price) * ledger.shares)
                .unwrap_or(Decimal::ZERO);
            PositionSnapshot {
                account,
                market_id,
                outcome_id,
                shares: ledger.shares,
                avg_price,
                cost_basis: ledger.cost_basis,
                realized_pnl: ledger.realized_pnl,
                unrealized_pnl,
                updated_at: updated_at.clone(),
            }
        })
        .collect::<Vec<_>>();

    for position in &positions {
        let wallet = wallets.entry(position.account.clone()).or_default();
        wallet.realized_pnl += position.realized_pnl;
    }

    let mut wallet_pnl = wallets
        .into_iter()
        .map(|(account, wallet)| {
            let unrealized_pnl = positions
                .iter()
                .filter(|position| position.account == account)
                .map(|position| position.unrealized_pnl)
                .sum();
            WalletPnlSnapshot {
                account,
                scope: "estimated_from_fills".to_string(),
                realized_pnl: wallet.realized_pnl,
                unrealized_pnl,
                trade_count: wallet.trade_count,
                market_count: wallet.markets.len(),
                audit_status: "estimated_from_fills".to_string(),
                evidence_json:
                    r#"{"source":"fills","settlement_events":false,"mark_price_source":"clob_asset_features"}"#
                    .to_string(),
                updated_at: updated_at.clone(),
            }
        })
        .collect::<Vec<_>>();

    wallet_pnl.sort_by(|a, b| b.realized_pnl.cmp(&a.realized_pnl));
    wallet_pnl.extend(settlement_wallet_pnl(&sorted, context, &updated_at));
    wallet_pnl.sort_by(|a, b| {
        a.account
            .cmp(&b.account)
            .then_with(|| a.scope.cmp(&b.scope))
    });
    Ok(WalletIntelligenceSnapshot {
        positions,
        wallet_pnl,
    })
}

fn settlement_wallet_pnl(
    fills: &[FillEvent],
    context: &WalletIntelligenceContext,
    updated_at: &str,
) -> Vec<WalletPnlSnapshot> {
    if context.settlement_events.is_empty() {
        return Vec::new();
    }
    let mut wallets = HashMap::<String, WalletLedger>::new();
    for fill in fills {
        let token = context.token_metadata.get(&fill.market_id);
        let market_id = token
            .map(|metadata| metadata.market_id.clone())
            .unwrap_or_else(|| fill.market_id.clone());
        let wallet = wallets.entry(fill.account.clone()).or_default();
        wallet.trade_count += 1;
        wallet.markets.insert(market_id);
        if fill.side == TradeSide::Buy {
            wallet.realized_pnl -= fill.price * fill.shares;
        }
    }
    for event in &context.settlement_events {
        let wallet = wallets.entry(event.account.clone()).or_default();
        wallet.realized_pnl += event.payout;
        wallet.markets.insert(event.market_id.clone());
    }
    wallets
        .into_iter()
        .filter(|(account, _)| {
            context
                .settlement_events
                .iter()
                .any(|event| event.account == *account)
        })
        .map(|(account, wallet)| {
            let event_count = context
                .settlement_events
                .iter()
                .filter(|event| event.account == account)
                .count();
            WalletPnlSnapshot {
                account,
                scope: "settlement_audited".to_string(),
                realized_pnl: wallet.realized_pnl,
                unrealized_pnl: Decimal::ZERO,
                trade_count: wallet.trade_count,
                market_count: wallet.markets.len(),
                audit_status: "settlement_audited".to_string(),
                evidence_json: format!(
                    r#"{{"source":"settlement_events","settlement_events":true,"event_count":{event_count}}}"#
                ),
                updated_at: updated_at.to_string(),
            }
        })
        .collect()
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

    #[test]
    fn uses_outcome_metadata_and_mark_price() {
        let fills = vec![fill(TradeSide::Buy, dec!(0.40), dec!(100))];
        let mut context = WalletIntelligenceContext::default();
        context.token_metadata.insert(
            "m1".to_string(),
            TokenMetadata {
                market_id: "condition-1".to_string(),
                outcome_id: "token-yes".to_string(),
            },
        );
        context
            .mark_prices
            .insert("token-yes".to_string(), dec!(0.55));

        let snapshot = build_wallet_intelligence_with_context(&fills, &context).expect("snapshot");

        assert_eq!(snapshot.positions[0].market_id, "condition-1");
        assert_eq!(snapshot.positions[0].outcome_id, "token-yes");
        assert_eq!(snapshot.positions[0].unrealized_pnl, dec!(15.00));
        assert_eq!(snapshot.wallet_pnl[0].unrealized_pnl, dec!(15.00));
    }

    #[test]
    fn adds_settlement_audited_wallet_pnl() {
        let fills = vec![fill(TradeSide::Buy, dec!(0.40), dec!(100))];
        let mut context = WalletIntelligenceContext::default();
        context.settlement_events.push(SettlementEvent {
            event_id: "redeem-1".to_string(),
            account: "0xabc".to_string(),
            market_id: "m1".to_string(),
            outcome_id: Some("m1".to_string()),
            event_type: "redemption".to_string(),
            amount: dec!(100),
            payout: dec!(100),
            settlement_price: Some(dec!(1)),
            timestamp: Utc::now().to_rfc3339(),
        });

        let snapshot = build_wallet_intelligence_with_context(&fills, &context).expect("snapshot");
        let audited = snapshot
            .wallet_pnl
            .iter()
            .find(|row| row.scope == "settlement_audited")
            .expect("audited pnl");

        assert_eq!(audited.realized_pnl, dec!(60.00));
        assert_eq!(audited.audit_status, "settlement_audited");
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
