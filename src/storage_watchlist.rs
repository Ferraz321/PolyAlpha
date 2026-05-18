use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::params;

use crate::storage::Storage;

#[derive(Debug, Clone)]
pub struct WatchlistEntry {
    pub account: String,
    pub label: Option<String>,
}

impl Storage {
    pub fn upsert_watchlist(&mut self, entries: &[WatchlistEntry], source: &str) -> Result<usize> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        let now = Utc::now().to_rfc3339();
        let mut count = 0usize;
        for entry in entries {
            count += tx.execute(
                r#"
                INSERT INTO wallet_watchlist (account, label, source, created_at, updated_at)
                VALUES (?1, ?2, ?3, ?4, ?4)
                ON CONFLICT(account) DO UPDATE SET
                    label = COALESCE(excluded.label, wallet_watchlist.label),
                    source = excluded.source,
                    updated_at = excluded.updated_at
                "#,
                params![entry.account.to_ascii_lowercase(), entry.label, source, now],
            )?;
        }
        tx.commit()?;
        Ok(count)
    }

    pub fn watchlist_label(&self, account: &str) -> Result<Option<String>> {
        self.init()?;
        self.raw_connection()
            .query_row(
                "SELECT label FROM wallet_watchlist WHERE account = ?1",
                params![account.to_ascii_lowercase()],
                |row| row.get(0),
            )
            .optional()
            .context("failed to load watchlist label")
    }
}

use rusqlite::OptionalExtension;
