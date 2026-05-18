use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::{Connection, params};

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
}

impl Storage {
    pub(crate) fn connection(&self) -> &Connection {
        self.raw_connection()
    }
}
