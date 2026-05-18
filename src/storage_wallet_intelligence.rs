use anyhow::Result;
use rusqlite::params;
use rust_decimal::Decimal;
use std::collections::HashMap;
use std::str::FromStr;

use crate::storage::Storage;
use crate::wallet_intelligence::{
    PositionSnapshot, TokenMetadata, WalletIntelligenceContext, WalletPnlSnapshot,
};

impl Storage {
    pub fn replace_wallet_intelligence(
        &mut self,
        positions: &[PositionSnapshot],
        wallet_pnl: &[WalletPnlSnapshot],
    ) -> Result<()> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        tx.execute("DELETE FROM positions", [])?;
        tx.execute("DELETE FROM wallet_pnl", [])?;

        for position in positions {
            tx.execute(
                r#"
                INSERT INTO positions (
                    account, market_id, outcome_id, shares, avg_price, cost_basis,
                    realized_pnl, unrealized_pnl, updated_at
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
                "#,
                params![
                    position.account,
                    position.market_id,
                    position.outcome_id,
                    position.shares.to_string(),
                    position.avg_price.to_string(),
                    position.cost_basis.to_string(),
                    position.realized_pnl.to_string(),
                    position.unrealized_pnl.to_string(),
                    position.updated_at,
                ],
            )?;
        }

        for pnl in wallet_pnl {
            tx.execute(
                r#"
                INSERT INTO wallet_pnl (
                    account, scope, realized_pnl, unrealized_pnl, trade_count,
                    market_count, audit_status, evidence_json, updated_at
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
                "#,
                params![
                    pnl.account,
                    pnl.scope,
                    pnl.realized_pnl.to_string(),
                    pnl.unrealized_pnl.to_string(),
                    pnl.trade_count,
                    pnl.market_count,
                    pnl.audit_status,
                    pnl.evidence_json,
                    pnl.updated_at,
                ],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn wallet_intelligence_context(&self) -> Result<WalletIntelligenceContext> {
        self.init()?;
        Ok(WalletIntelligenceContext {
            token_metadata: self.wallet_token_metadata()?,
            mark_prices: self.latest_mark_prices()?,
        })
    }

    fn wallet_token_metadata(&self) -> Result<HashMap<String, TokenMetadata>> {
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT token_id, COALESCE(condition_id, market_slug, event_slug, token_id)
            FROM market_tokens
            "#,
        )?;
        let rows = stmt.query_map([], |row| {
            let token_id: String = row.get(0)?;
            let market_id: String = row.get(1)?;
            Ok((
                token_id.clone(),
                TokenMetadata {
                    market_id,
                    outcome_id: token_id,
                },
            ))
        })?;
        Ok(rows.collect::<rusqlite::Result<HashMap<_, _>>>()?)
    }

    fn latest_mark_prices(&self) -> Result<HashMap<String, Decimal>> {
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT asset_id, best_bid, best_ask, last_trade_price
            FROM clob_asset_features
            "#,
        )?;
        let rows = stmt.query_map([], |row| {
            let asset_id: String = row.get(0)?;
            let best_bid: Option<String> = row.get(1)?;
            let best_ask: Option<String> = row.get(2)?;
            let last_trade_price: Option<String> = row.get(3)?;
            Ok((asset_id, mark_price(best_bid, best_ask, last_trade_price)))
        })?;
        Ok(rows
            .filter_map(|row| match row {
                Ok((asset_id, Some(price))) => Some(Ok((asset_id, price))),
                Ok((_, None)) => None,
                Err(error) => Some(Err(error)),
            })
            .collect::<rusqlite::Result<HashMap<_, _>>>()?)
    }
}

fn mark_price(
    best_bid: Option<String>,
    best_ask: Option<String>,
    last_trade_price: Option<String>,
) -> Option<Decimal> {
    let bid = best_bid.as_deref().and_then(parse_decimal);
    let ask = best_ask.as_deref().and_then(parse_decimal);
    match (bid, ask) {
        (Some(bid), Some(ask)) => Some((bid + ask) / Decimal::from(2u64)),
        _ => last_trade_price.as_deref().and_then(parse_decimal),
    }
}

fn parse_decimal(value: &str) -> Option<Decimal> {
    Decimal::from_str(value).ok()
}
