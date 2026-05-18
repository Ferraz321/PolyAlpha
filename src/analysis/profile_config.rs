use std::fs;
use std::path::Path;

use anyhow::{Context, Result};
use rust_decimal::Decimal;
use serde::Deserialize;

use crate::model::AccountMetrics;
use crate::tagging::{AccountTag, SmartMoneyTier};

#[derive(Debug, Clone, Deserialize)]
pub struct AccountProfile {
    pub id: String,
    pub family: String,
    pub tier: String,
    pub tag: Option<String>,
    #[serde(default)]
    pub default_pool: bool,
    #[serde(default)]
    pub priority: i64,
    #[serde(default)]
    pub rules: Vec<MetricRule>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MetricRule {
    pub metric: String,
    pub min: Option<String>,
    pub max: Option<String>,
}

#[derive(Debug, Clone)]
pub struct ProfileMatch {
    pub id: String,
    pub family: String,
    pub tier: SmartMoneyTier,
    pub tag: Option<AccountTag>,
    pub default_pool: bool,
}

pub fn load_account_profiles(path: &Path) -> Result<Vec<AccountProfile>> {
    if !path.exists() {
        return Ok(Vec::new());
    }

    let mut profiles = Vec::new();
    for entry in fs::read_dir(path).context("failed to read account profile directory")? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
            continue;
        }
        let content = fs::read_to_string(&path)
            .with_context(|| format!("failed to read profile {}", path.display()))?;
        profiles.push(
            serde_json::from_str::<AccountProfile>(&content)
                .with_context(|| format!("failed to parse profile {}", path.display()))?,
        );
    }
    profiles.sort_by(|a, b| b.priority.cmp(&a.priority).then_with(|| a.id.cmp(&b.id)));
    Ok(profiles)
}

pub fn match_profile(
    metrics: &AccountMetrics,
    profiles: &[AccountProfile],
) -> Option<ProfileMatch> {
    profiles
        .iter()
        .find(|profile| profile.rules.iter().all(|rule| rule.matches(metrics)))
        .map(|profile| ProfileMatch {
            id: profile.id.clone(),
            family: profile.family.clone(),
            tier: parse_tier(&profile.tier),
            tag: profile.tag.as_deref().and_then(parse_tag),
            default_pool: profile.default_pool,
        })
}

impl MetricRule {
    fn matches(&self, metrics: &AccountMetrics) -> bool {
        let Some(value) = metric_value(metrics, &self.metric) else {
            return false;
        };
        if let Some(min) = self.min.as_deref().and_then(parse_decimal) {
            if value < min {
                return false;
            }
        }
        if let Some(max) = self.max.as_deref().and_then(parse_decimal) {
            if value > max {
                return false;
            }
        }
        true
    }
}

fn metric_value(metrics: &AccountMetrics, name: &str) -> Option<Decimal> {
    Some(match name {
        "total_volume" => metrics.total_volume,
        "avg_trade_size" => metrics.avg_trade_size,
        "trade_count" => Decimal::from(metrics.trade_count),
        "distinct_markets" => Decimal::from(metrics.distinct_markets),
        "closed_markets" => Decimal::from(metrics.closed_markets),
        "total_pnl" => metrics.total_pnl,
        "win_rate" => metrics.win_rate,
        "profit_loss_ratio" => metrics.profit_loss_ratio,
        "expectancy" => metrics.expectancy,
        "max_single_market_pnl_share" => metrics.max_single_market_pnl_share,
        "maker_ratio" => metrics.maker_ratio,
        "sector_concentration" => metrics.sector_concentration,
        _ => return None,
    })
}

fn parse_decimal(value: &str) -> Option<Decimal> {
    value.parse().ok()
}

fn parse_tier(value: &str) -> SmartMoneyTier {
    match value {
        "core_smart_money" => SmartMoneyTier::CoreSmartMoney,
        "candidate_smart_money" => SmartMoneyTier::CandidateSmartMoney,
        "watchlist" => SmartMoneyTier::Watchlist,
        _ => SmartMoneyTier::NotSmartMoney,
    }
}

fn parse_tag(value: &str) -> Option<AccountTag> {
    Some(match value {
        "stable_alpha_wallet" => AccountTag::StableAlphaWallet,
        "information_edge_wallet" => AccountTag::InformationEdgeWallet,
        "stat_arb_market_maker_bot" => AccountTag::StatArbMarketMakerBot,
        "swing_trader" => AccountTag::SwingTrader,
        "one_shot_whale" => AccountTag::OneShotWhale,
        "high_volume_noise" => AccountTag::HighVolumeNoise,
        "unprofitable_trader" => AccountTag::UnprofitableTrader,
        _ => return None,
    })
}
