use std::collections::HashSet;
use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::filter::{FunnelConfig, evaluate};
use oktrader_alpha::metrics::{MetricsConfig, compute_account_metrics};
use oktrader_alpha::model::FillEvent;
use oktrader_alpha::tagging::{
    AccountClassification, AccountTag, SmartMoneyTier, classify_profile,
};
use serde::Serialize;

use crate::cli::ReportFilterArgs;

#[derive(Debug, Clone, Serialize)]
pub struct AccountReport {
    #[serde(flatten)]
    pub metrics: oktrader_alpha::model::AccountMetrics,
    pub passed_funnel: bool,
    pub failed_reasons: Vec<String>,
    #[serde(flatten)]
    pub classification: AccountClassification,
}

#[derive(Debug, Clone)]
pub struct ReportFilter {
    tiers: HashSet<SmartMoneyTier>,
    tags: HashSet<AccountTag>,
    wallet_pool: Option<HashSet<String>>,
}

impl ReportFilterArgs {
    pub fn load(self) -> Result<ReportFilter> {
        let wallet_pool = match self.wallet_pool {
            Some(path) => Some(read_wallet_pool(&path)?),
            None => None,
        };

        Ok(ReportFilter {
            tiers: self.tiers.into_iter().collect(),
            tags: self.tags.into_iter().collect(),
            wallet_pool,
        })
    }
}

pub fn build_reports(
    fills: Vec<FillEvent>,
    passed_only: bool,
    close_loop_alpha: rust_decimal::Decimal,
) -> Result<Vec<AccountReport>> {
    let (metrics, _closed_loops) =
        compute_account_metrics(&fills, MetricsConfig { close_loop_alpha })?;
    let config = FunnelConfig::default();

    Ok(metrics
        .into_iter()
        .filter_map(|metrics| {
            let decision = evaluate(&metrics, &config);
            if passed_only && !decision.passed {
                return None;
            }

            Some(AccountReport {
                classification: classify_profile(&metrics),
                metrics,
                passed_funnel: decision.passed,
                failed_reasons: decision.failed_reasons,
            })
        })
        .collect())
}

pub fn filter_reports<'a>(
    reports: &'a [AccountReport],
    filters: &ReportFilter,
) -> Vec<&'a AccountReport> {
    reports
        .iter()
        .filter(|report| {
            filters.tiers.is_empty()
                || filters
                    .tiers
                    .contains(&report.classification.smart_money_tier)
        })
        .filter(|report| {
            filters.tags.is_empty() || filters.tags.contains(&report.classification.primary_tag)
        })
        .filter(|report| {
            filters.wallet_pool.as_ref().is_none_or(|wallet_pool| {
                wallet_pool.contains(&report.metrics.account.to_ascii_lowercase())
            })
        })
        .collect()
}

fn read_wallet_pool(path: &std::path::Path) -> Result<HashSet<String>> {
    let content = fs::read_to_string(path).context("failed to read wallet pool")?;
    Ok(content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(|line| line.to_ascii_lowercase())
        .collect())
}
