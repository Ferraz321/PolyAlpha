use anyhow::Result;
use rusqlite::params;

use crate::storage::Storage;
use crate::wallet_intelligence::{PositionSnapshot, WalletPnlSnapshot};

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
}
