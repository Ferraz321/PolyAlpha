use std::collections::HashMap;

use anyhow::Result;
use chrono::Utc;
use rust_decimal::Decimal;

use crate::clob_features::features_from_payload;
use crate::model::{FillEvent, TradeSide};
use crate::storage::Storage;
use crate::storage_types::WalletMicrostructureMetric;

#[derive(Debug, Clone, Copy)]
pub struct JoinConfig {
    pub pre_secs: i64,
    pub post_secs: i64,
    pub event_limit: usize,
}

#[derive(Default)]
struct Accumulator {
    observed: usize,
    spread_sum: Decimal,
    ofi_sum: Decimal,
    favorable: usize,
}

pub fn build_wallet_microstructure(
    storage: &Storage,
    fills: &[FillEvent],
    config: JoinConfig,
) -> Result<Vec<WalletMicrostructureMetric>> {
    let mut accounts = HashMap::<String, Accumulator>::new();
    for fill in fills {
        let Some((spread, ofi)) = closest_microstructure(storage, fill, config)? else {
            continue;
        };
        let account = accounts.entry(fill.account.clone()).or_default();
        account.observed += 1;
        account.spread_sum += spread;
        account.ofi_sum += ofi;
        if is_favorable(fill.side, ofi) {
            account.favorable += 1;
        }
    }

    let updated_at = Utc::now().to_rfc3339();
    let mut metrics = accounts
        .into_iter()
        .filter_map(|(account, acc)| {
            (acc.observed > 0).then(|| WalletMicrostructureMetric {
                account,
                observed_fills: acc.observed,
                avg_spread: (acc.spread_sum / Decimal::from(acc.observed)).to_string(),
                avg_ofi: (acc.ofi_sum / Decimal::from(acc.observed)).to_string(),
                favorable_ofi_rate: ratio(acc.favorable, acc.observed).to_string(),
                updated_at: updated_at.clone(),
            })
        })
        .collect::<Vec<_>>();
    metrics.sort_by(|a, b| b.observed_fills.cmp(&a.observed_fills));
    Ok(metrics)
}

fn closest_microstructure(
    storage: &Storage,
    fill: &FillEvent,
    config: JoinConfig,
) -> Result<Option<(Decimal, Decimal)>> {
    let events = storage.clob_events_around_fill(
        &fill.market_id,
        fill.timestamp,
        config.pre_secs,
        config.post_secs,
        config.event_limit,
    )?;
    for event in events {
        let features = features_from_payload(&event.payload, &event.received_at)?;
        if let Some(feature) = features.into_iter().find(|f| f.asset_id == fill.market_id) {
            let spread = parse_decimal(feature.spread.as_deref()).unwrap_or(Decimal::ZERO);
            let ofi = parse_decimal(feature.ofi.as_deref()).unwrap_or(Decimal::ZERO);
            return Ok(Some((spread, ofi)));
        }
    }
    Ok(None)
}

fn parse_decimal(value: Option<&str>) -> Option<Decimal> {
    value?.parse().ok()
}

fn is_favorable(side: TradeSide, ofi: Decimal) -> bool {
    match side {
        TradeSide::Buy => ofi > Decimal::ZERO,
        TradeSide::Sell => ofi < Decimal::ZERO,
    }
}

fn ratio(numerator: usize, denominator: usize) -> Decimal {
    if denominator == 0 {
        Decimal::ZERO
    } else {
        Decimal::from(numerator) / Decimal::from(denominator)
    }
}
