use std::path::Path;
use std::str::FromStr;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{Connection, OptionalExtension, params};
use rust_decimal::Decimal;

use crate::model::{FillEvent, LiquidityRole, TradeSide};
use crate::storage_types::{DbStats, stable_fill_key};

pub struct Storage {
    conn: Connection,
}

#[derive(Debug)]
pub struct InsertSummary {
    pub inserted_fills: usize,
    pub new_wallets: usize,
}

impl Storage {
    pub(crate) fn raw_connection(&self) -> &Connection {
        &self.conn
    }

    pub(crate) fn raw_connection_mut(&mut self) -> &mut Connection {
        &mut self.conn
    }

    pub fn open(path: impl AsRef<Path>) -> Result<Self> {
        if let Some(parent) = path.as_ref().parent() {
            std::fs::create_dir_all(parent).context("failed to create database directory")?;
        }

        let conn = Connection::open(path).context("failed to open sqlite database")?;
        conn.pragma_update(None, "journal_mode", "WAL")?;
        conn.pragma_update(None, "foreign_keys", "ON")?;

        Ok(Self { conn })
    }

    pub fn init(&self) -> Result<()> {
        self.conn.execute_batch(include_str!("../sql/schema.sql"))?;
        Ok(())
    }

    pub fn insert_fills(&mut self, fills: &[FillEvent]) -> Result<InsertSummary> {
        self.init()?;
        let tx = self.conn.transaction()?;
        let mut inserted_fills = 0usize;
        let mut new_wallets = 0usize;

        for fill in fills {
            let wallet_exists = tx
                .query_row(
                    "SELECT 1 FROM wallets WHERE account = ?1",
                    params![fill.account],
                    |_| Ok(()),
                )
                .optional()?
                .is_some();

            let changed = tx.execute(
                r#"
                INSERT OR IGNORE INTO fills (
                    account, market_id, condition_id, event_slug, sector, side, role,
                    price, shares, timestamp, tx_hash, order_hash, stable_key
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)
                "#,
                params![
                    fill.account,
                    fill.market_id,
                    fill.condition_id,
                    fill.event_slug,
                    fill.sector,
                    fill.side.to_string(),
                    fill.role.to_string(),
                    fill.price.to_string(),
                    fill.shares.to_string(),
                    fill.timestamp.to_rfc3339(),
                    fill.tx_hash,
                    fill.order_hash,
                    stable_fill_key(fill),
                ],
            )?;

            if changed == 1 {
                inserted_fills += 1;
                tx.execute(
                    r#"
                    INSERT INTO wallets (account, first_seen_at, last_seen_at, total_trades)
                    VALUES (?1, ?2, ?2, 1)
                    ON CONFLICT(account) DO UPDATE SET
                        last_seen_at = excluded.last_seen_at,
                        total_trades = wallets.total_trades + 1,
                        status = CASE
                            WHEN wallets.status = 'cold' THEN 'active'
                            ELSE wallets.status
                        END
                    "#,
                    params![fill.account, fill.timestamp.to_rfc3339()],
                )?;

                if !wallet_exists {
                    new_wallets += 1;
                }
                tx.execute(
                    r#"
                    INSERT INTO dirty_wallets (account, reason, updated_at)
                    VALUES (?1, 'new_fill', ?2)
                    ON CONFLICT(account) DO UPDATE SET
                        reason = excluded.reason,
                        updated_at = excluded.updated_at
                    "#,
                    params![fill.account, Utc::now().to_rfc3339()],
                )?;
            }
        }

        tx.commit()?;
        Ok(InsertSummary {
            inserted_fills,
            new_wallets,
        })
    }

    pub fn load_fills(&self) -> Result<Vec<FillEvent>> {
        self.init()?;
        let mut stmt = self.conn.prepare(
            r#"
            SELECT account, market_id, condition_id, event_slug, sector, side, role,
                   price, shares, timestamp, tx_hash, order_hash
            FROM fills
            ORDER BY timestamp ASC, id ASC
            "#,
        )?;

        let rows = stmt.query_map([], |row| {
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
                price: Decimal::from_str(&price).map_err(parse_sql_error)?,
                shares: Decimal::from_str(&shares).map_err(parse_sql_error)?,
                timestamp: DateTime::parse_from_rfc3339(&timestamp)
                    .map_err(parse_sql_error)?
                    .with_timezone(&Utc),
                tx_hash: row.get(10)?,
                order_hash: row.get(11)?,
            })
        })?;

        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load fills")
    }

    pub fn replace_matched_accounts<T>(
        &mut self,
        reports: &[T],
        account: impl Fn(&T) -> &str,
        to_json: impl Fn(&T) -> Result<String>,
    ) -> Result<()> {
        self.init()?;
        let tx = self.conn.transaction()?;
        tx.execute("DELETE FROM matched_accounts", [])?;
        let updated_at = Utc::now().to_rfc3339();

        for report in reports {
            tx.execute(
                r#"
                INSERT INTO matched_accounts (account, report_json, updated_at)
                VALUES (?1, ?2, ?3)
                "#,
                params![account(report), to_json(report)?, updated_at],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn stats(&self) -> Result<DbStats> {
        self.init()?;
        Ok(DbStats {
            fills: count(&self.conn, "fills")?,
            wallets: count(&self.conn, "wallets")?,
            account_metrics: count(&self.conn, "account_metrics")?,
            matched_accounts: count(&self.conn, "matched_accounts")?,
            raw_evm_logs: count(&self.conn, "raw_evm_logs")?,
            raw_clob_events: count(&self.conn, "raw_clob_events")?,
            clob_asset_features: count(&self.conn, "clob_asset_features")?,
            dirty_wallets: count(&self.conn, "dirty_wallets")?,
        })
    }

    pub fn matched_account_json(&self) -> Result<Vec<String>> {
        self.init()?;
        let mut stmt = self
            .conn
            .prepare("SELECT report_json FROM matched_accounts ORDER BY updated_at DESC")?;
        let rows = stmt.query_map([], |row| row.get(0))?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load matched accounts")
    }

    pub fn set_state(&self, name: &str, value: &str) -> Result<()> {
        self.init()?;
        self.conn.execute(
            r#"
            INSERT INTO scanner_state (name, value, updated_at)
            VALUES (?1, ?2, ?3)
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            "#,
            params![name, value, Utc::now().to_rfc3339()],
        )?;
        Ok(())
    }

    pub fn get_state(&self, name: &str) -> Result<Option<String>> {
        self.init()?;
        self.conn
            .query_row(
                "SELECT value FROM scanner_state WHERE name = ?1",
                params![name],
                |row| row.get(0),
            )
            .optional()
            .context("failed to read scanner state")
    }
}

fn count(conn: &Connection, table: &str) -> Result<usize> {
    let sql = format!("SELECT COUNT(*) FROM {table}");
    Ok(conn.query_row(&sql, [], |row| row.get::<_, i64>(0))? as usize)
}

fn parse_sql_error(error: impl std::error::Error + Send + Sync + 'static) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(error))
}
