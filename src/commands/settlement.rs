use anyhow::{Context, Result, ensure};
use rust_decimal::Decimal;
use serde::Deserialize;
use std::str::FromStr;

use oktrader_alpha::storage::Storage;
use oktrader_alpha::wallet_intelligence::SettlementEvent;

use crate::app::cli::ImportSettlementsArgs;

#[derive(Debug, Deserialize)]
struct SettlementCsvRow {
    event_id: Option<String>,
    account: String,
    market_id: String,
    outcome_id: Option<String>,
    event_type: String,
    amount: Option<String>,
    payout: Option<String>,
    settlement_price: Option<String>,
    timestamp: String,
    tx_hash: Option<String>,
    log_index: Option<u64>,
}

pub fn import_settlements(args: ImportSettlementsArgs) -> Result<()> {
    let mut reader = csv::Reader::from_path(&args.input)
        .with_context(|| format!("failed to read {}", args.input.display()))?;
    let mut events = Vec::new();
    for row in reader.deserialize::<SettlementCsvRow>() {
        events.push(row?.into_event()?);
    }
    let mut storage = Storage::open(&args.db)?;
    let changed = storage.upsert_settlement_events(&events)?;
    println!(
        "settlements: input={} events={} upserted={}",
        args.input.display(),
        events.len(),
        changed
    );
    Ok(())
}

impl SettlementCsvRow {
    fn into_event(self) -> Result<SettlementEvent> {
        ensure!(
            self.account.starts_with("0x"),
            "settlement account must be a wallet address"
        );
        ensure!(!self.market_id.is_empty(), "settlement market_id is empty");
        ensure!(!self.timestamp.is_empty(), "settlement timestamp is empty");
        let event_id = self.event_id.unwrap_or_else(|| {
            format!(
                "{}:{}:{}:{}",
                self.tx_hash.as_deref().unwrap_or("manual"),
                self.log_index.unwrap_or(0),
                self.account,
                self.market_id
            )
        });
        Ok(SettlementEvent {
            event_id,
            account: self.account,
            market_id: self.market_id,
            outcome_id: self.outcome_id,
            event_type: self.event_type,
            amount: parse_decimal(self.amount.as_deref().unwrap_or("0"))?,
            payout: parse_decimal(self.payout.as_deref().unwrap_or("0"))?,
            settlement_price: self
                .settlement_price
                .as_deref()
                .map(parse_decimal)
                .transpose()?,
            timestamp: self.timestamp,
        })
    }
}

fn parse_decimal(value: &str) -> Result<Decimal> {
    Decimal::from_str(value).with_context(|| format!("invalid decimal {value}"))
}
