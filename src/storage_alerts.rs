use std::str::FromStr;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::params;
use rust_decimal::Decimal;

use crate::model::{FillEvent, LiquidityRole, TradeSide};
use crate::storage::Storage;

pub struct StoredFill {
    pub id: i64,
    pub fill: FillEvent,
    pub matched_report_json: Option<String>,
}

impl Storage {
    pub fn max_fill_id(&self) -> Result<i64> {
        self.init()?;
        Ok(self.raw_connection().query_row(
            "SELECT COALESCE(MAX(id), 0) FROM fills",
            [],
            |row| row.get(0),
        )?)
    }

    pub fn fills_after(
        &self,
        after_id: i64,
        limit: usize,
        matched_only: bool,
    ) -> Result<Vec<StoredFill>> {
        self.init()?;
        let matched_clause = if matched_only {
            "AND ma.account IS NOT NULL"
        } else {
            ""
        };
        let sql = format!(
            r#"
            SELECT f.id, f.account, f.market_id, f.condition_id, f.event_slug, f.sector,
                   f.side, f.role, f.price, f.shares, f.timestamp, f.tx_hash, f.order_hash,
                   ma.report_json
            FROM fills f
            LEFT JOIN matched_accounts ma ON ma.account = f.account
            WHERE f.id > ?1 {matched_clause}
            ORDER BY f.id ASC
            LIMIT ?2
            "#
        );
        let mut stmt = self.raw_connection().prepare(&sql)?;
        let rows = stmt.query_map(params![after_id, limit], stored_fill_from_row)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load fill alerts")
    }
}

fn stored_fill_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<StoredFill> {
    let side: String = row.get(6)?;
    let role: String = row.get(7)?;
    let price: String = row.get(8)?;
    let shares: String = row.get(9)?;
    let timestamp: String = row.get(10)?;
    Ok(StoredFill {
        id: row.get(0)?,
        fill: FillEvent {
            account: row.get(1)?,
            market_id: row.get(2)?,
            condition_id: row.get(3)?,
            event_slug: row.get(4)?,
            sector: row.get(5)?,
            side: TradeSide::from_str(&side).map_err(parse_sql_error)?,
            role: LiquidityRole::from_str(&role).map_err(parse_sql_error)?,
            price: Decimal::from_str(&price).map_err(parse_sql_error)?,
            shares: Decimal::from_str(&shares).map_err(parse_sql_error)?,
            timestamp: DateTime::parse_from_rfc3339(&timestamp)
                .map_err(parse_sql_error)?
                .with_timezone(&Utc),
            tx_hash: row.get(11)?,
            order_hash: row.get(12)?,
        },
        matched_report_json: row.get(13)?,
    })
}

fn parse_sql_error(error: impl std::error::Error + Send + Sync + 'static) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(error))
}
