use anyhow::Result;
use rust_decimal::Decimal;

use crate::model::{AccountMetrics, FillEvent};
use crate::tagging::AccountClassification;

pub struct MetricParts {
    pub account: String,
    pub metrics_json: String,
    pub classification_json: String,
    pub passed_funnel: bool,
    pub failed_reasons_json: String,
}

#[derive(Debug)]
pub struct DbStats {
    pub fills: usize,
    pub wallets: usize,
    pub account_metrics: usize,
    pub matched_accounts: usize,
}

pub fn metric_parts(
    metrics: &AccountMetrics,
    classification: &AccountClassification,
    passed_funnel: bool,
    failed_reasons: &[String],
) -> Result<MetricParts> {
    Ok(MetricParts {
        account: metrics.account.clone(),
        metrics_json: serde_json::to_string(metrics)?,
        classification_json: serde_json::to_string(classification)?,
        passed_funnel,
        failed_reasons_json: serde_json::to_string(failed_reasons)?,
    })
}

pub fn stable_fill_key(fill: &FillEvent) -> String {
    format!(
        "{}:{}:{}:{}:{}:{}",
        fill.tx_hash.as_deref().unwrap_or(""),
        fill.account,
        fill.condition_id.as_deref().unwrap_or(""),
        fill.market_id,
        fill.side,
        fill.timestamp.timestamp()
    )
}

pub fn scale_6(value: Decimal) -> Decimal {
    value / Decimal::from(1_000_000u64)
}
