use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::{Connection, params};

use crate::model::{FillEvent, LiquidityRole, TradeSide};
use crate::storage::Storage;

impl Storage {
    pub fn mark_dirty_wallet(&self, account: &str, reason: &str) -> Result<()> {
        self.init()?;
        self.connection().execute(
            r#"
            INSERT INTO dirty_wallets (account, reason, updated_at)
            VALUES (?1, ?2, ?3)
            ON CONFLICT(account) DO UPDATE SET
                reason = excluded.reason,
                updated_at = excluded.updated_at
            "#,
            params![account, reason, Utc::now().to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn dirty_wallets(&self, limit: usize) -> Result<Vec<String>> {
        self.init()?;
        let mut stmt = self
            .connection()
            .prepare("SELECT account FROM dirty_wallets ORDER BY updated_at ASC LIMIT ?1")?;
        let rows = stmt.query_map(params![limit as i64], |row| row.get(0))?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load dirty wallets")
    }

    pub fn clear_dirty_wallets(&self, accounts: &[String]) -> Result<()> {
        self.init()?;
        for account in accounts {
            self.connection().execute(
                "DELETE FROM dirty_wallets WHERE account = ?1",
                params![account],
            )?;
        }
        Ok(())
    }

    pub fn update_wallet_status(&self, account: &str, status: &str) -> Result<()> {
        self.init()?;
        self.connection().execute(
            "UPDATE wallets SET status = ?2 WHERE account = ?1",
            params![account, status],
        )?;
        Ok(())
    }

    pub fn refresh_wallet_statuses(&self) -> Result<usize> {
        self.init()?;
        let changed = self.connection().execute(
            r#"
            UPDATE wallets
            SET status = CASE
                WHEN datetime(last_seen_at) < datetime('now', '-30 days') THEN 'cold'
                WHEN total_trades >= 30 THEN 'watchlist'
                ELSE status
            END
            WHERE status NOT IN ('matched', 'excluded')
            "#,
            [],
        )?;
        Ok(changed)
    }

    pub fn load_fills_for_wallets(&self, accounts: &[String]) -> Result<Vec<FillEvent>> {
        self.init()?;
        let mut fills = Vec::new();
        for account in accounts {
            fills.extend(self.load_fills_for_wallet(account)?);
        }
        Ok(fills)
    }

    fn load_fills_for_wallet(&self, account: &str) -> Result<Vec<FillEvent>> {
        let mut stmt = self.connection().prepare(
            r#"
            SELECT account, market_id, condition_id, event_slug, sector, side, role,
                   price, shares, timestamp, tx_hash, order_hash
            FROM fills
            WHERE account = ?1
            ORDER BY timestamp ASC, id ASC
            "#,
        )?;
        let rows = stmt.query_map(params![account], fill_from_row)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load wallet fills")
    }
}

impl Storage {
    pub(crate) fn connection(&self) -> &Connection {
        self.raw_connection()
    }
}

fn fill_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<FillEvent> {
    use std::str::FromStr;

    let side: String = row.get(5)?;
    let role: String = row.get(6)?;
    let price: String = row.get(7)?;
    let shares: String = row.get(8)?;
    let timestamp: String = row.get(9)?;

    Ok(FillEvent {
        account: row.get(0)?,
        market_id: row.get(1)?,
        condition_id: row.get(2)?,
        event_slug: row.get(3)?,
        sector: row.get(4)?,
        side: TradeSide::from_str(&side).map_err(parse_sql_error)?,
        role: LiquidityRole::from_str(&role).map_err(parse_sql_error)?,
        price: rust_decimal::Decimal::from_str(&price).map_err(parse_sql_error)?,
        shares: rust_decimal::Decimal::from_str(&shares).map_err(parse_sql_error)?,
        timestamp: chrono::DateTime::parse_from_rfc3339(&timestamp)
            .map_err(parse_sql_error)?
            .with_timezone(&chrono::Utc),
        tx_hash: row.get(10)?,
        order_hash: row.get(11)?,
    })
}

fn parse_sql_error(error: impl std::error::Error + Send + Sync + 'static) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(error))
}
