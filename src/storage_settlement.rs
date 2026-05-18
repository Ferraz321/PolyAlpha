use anyhow::{Context, Result};
use rusqlite::params;
use rust_decimal::Decimal;
use std::str::FromStr;

use crate::storage::Storage;
use crate::wallet_intelligence::SettlementEvent;

impl Storage {
    pub fn upsert_settlement_events(&mut self, events: &[SettlementEvent]) -> Result<usize> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        let mut changed = 0usize;
        for event in events {
            changed += tx.execute(
                r#"
                INSERT INTO settlement_events (
                    event_id, account, market_id, outcome_id, event_type, amount,
                    payout, settlement_price, timestamp, raw_json
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
                ON CONFLICT(event_id) DO UPDATE SET
                    account = excluded.account,
                    market_id = excluded.market_id,
                    outcome_id = excluded.outcome_id,
                    event_type = excluded.event_type,
                    amount = excluded.amount,
                    payout = excluded.payout,
                    settlement_price = excluded.settlement_price,
                    timestamp = excluded.timestamp,
                    raw_json = excluded.raw_json
                "#,
                params![
                    event.event_id,
                    event.account,
                    event.market_id,
                    event.outcome_id,
                    event.event_type,
                    event.amount.to_string(),
                    event.payout.to_string(),
                    event.settlement_price.map(|value| value.to_string()),
                    event.timestamp,
                    serde_json::to_string(event)?,
                ],
            )?;
        }
        tx.commit()?;
        Ok(changed)
    }

    pub fn load_settlement_events(&self) -> Result<Vec<SettlementEvent>> {
        self.init()?;
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT event_id, account, market_id, outcome_id, event_type, amount,
                   payout, settlement_price, timestamp
            FROM settlement_events
            ORDER BY timestamp ASC
            "#,
        )?;
        let rows = stmt.query_map([], |row| {
            let amount: String = row.get(5)?;
            let payout: String = row.get(6)?;
            let settlement_price: Option<String> = row.get(7)?;
            Ok(SettlementEvent {
                event_id: row.get(0)?,
                account: row.get(1)?,
                market_id: row.get(2)?,
                outcome_id: row.get(3)?,
                event_type: row.get(4)?,
                amount: parse_decimal(&amount)?,
                payout: parse_decimal(&payout)?,
                settlement_price: settlement_price.as_deref().map(parse_decimal).transpose()?,
                timestamp: row.get(8)?,
            })
        })?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load settlement events")
            .map_err(Into::into)
    }
}

fn parse_decimal(value: &str) -> rusqlite::Result<Decimal> {
    Decimal::from_str(value).map_err(|error| {
        rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(error))
    })
}
