use clap::ValueEnum;
use rust_decimal_macros::dec;
use serde::{Deserialize, Serialize};

use crate::model::AccountMetrics;

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq, Hash, ValueEnum)]
#[serde(rename_all = "snake_case")]
pub enum SmartMoneyTier {
    CoreSmartMoney,
    CandidateSmartMoney,
    Watchlist,
    NotSmartMoney,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq, Hash, ValueEnum)]
#[serde(rename_all = "snake_case")]
pub enum AccountTag {
    StableAlphaWallet,
    InformationEdgeWallet,
    StatArbMarketMakerBot,
    SwingTrader,
    HighVolumeNoise,
    OneShotWhale,
    SmallSampleNoise,
    UnprofitableTrader,
    Unclassified,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RiskFlag {
    SmallSample,
    OneMarketConcentration,
    LowClosedMarketCount,
    LowProfitLossRatio,
    NegativePnl,
    MakerRatioUnavailableOrLow,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct AccountClassification {
    pub smart_money_tier: SmartMoneyTier,
    pub primary_tag: AccountTag,
    pub risk_flags: Vec<RiskFlag>,
}

pub fn classify(metrics: &AccountMetrics) -> AccountTag {
    classify_profile(metrics).primary_tag
}

pub fn classify_profile(metrics: &AccountMetrics) -> AccountClassification {
    let risk_flags = risk_flags(metrics);
    let primary_tag = primary_tag(metrics);
    let smart_money_tier = smart_money_tier(metrics, &primary_tag, &risk_flags);

    AccountClassification {
        smart_money_tier,
        primary_tag,
        risk_flags,
    }
}

fn primary_tag(metrics: &AccountMetrics) -> AccountTag {
    if metrics.total_pnl < dec!(0) {
        return AccountTag::UnprofitableTrader;
    }

    if metrics.closed_markets < 5 || metrics.trade_count < 30 {
        return AccountTag::SmallSampleNoise;
    }

    if metrics.max_single_market_pnl_share >= dec!(0.40) && metrics.total_pnl >= dec!(10000) {
        return AccountTag::OneShotWhale;
    }

    if is_stable_alpha(metrics) {
        return AccountTag::StableAlphaWallet;
    }

    if is_information_edge(metrics) {
        return AccountTag::InformationEdgeWallet;
    }

    if is_market_maker_bot(metrics) {
        return AccountTag::StatArbMarketMakerBot;
    }

    if is_swing_trader(metrics) {
        return AccountTag::SwingTrader;
    }

    if metrics.total_volume >= dec!(250000) && metrics.total_pnl <= dec!(0) {
        return AccountTag::HighVolumeNoise;
    }

    AccountTag::Unclassified
}

fn smart_money_tier(
    metrics: &AccountMetrics,
    primary_tag: &AccountTag,
    risk_flags: &[RiskFlag],
) -> SmartMoneyTier {
    if matches!(
        primary_tag,
        AccountTag::SmallSampleNoise
            | AccountTag::OneShotWhale
            | AccountTag::HighVolumeNoise
            | AccountTag::UnprofitableTrader
            | AccountTag::Unclassified
    ) {
        return SmartMoneyTier::NotSmartMoney;
    }

    if risk_flags.contains(&RiskFlag::OneMarketConcentration)
        || risk_flags.contains(&RiskFlag::SmallSample)
        || risk_flags.contains(&RiskFlag::NegativePnl)
    {
        return SmartMoneyTier::Watchlist;
    }

    if is_core_smart_money(metrics) {
        return SmartMoneyTier::CoreSmartMoney;
    }

    SmartMoneyTier::CandidateSmartMoney
}

fn risk_flags(metrics: &AccountMetrics) -> Vec<RiskFlag> {
    let mut flags = Vec::new();

    if metrics.trade_count < 100 {
        flags.push(RiskFlag::SmallSample);
    }
    if metrics.closed_markets < 15 {
        flags.push(RiskFlag::LowClosedMarketCount);
    }
    if metrics.max_single_market_pnl_share >= dec!(0.40) {
        flags.push(RiskFlag::OneMarketConcentration);
    }
    if metrics.profit_loss_ratio > dec!(0) && metrics.profit_loss_ratio < dec!(1.2) {
        flags.push(RiskFlag::LowProfitLossRatio);
    }
    if metrics.total_pnl < dec!(0) {
        flags.push(RiskFlag::NegativePnl);
    }
    if metrics.maker_ratio < dec!(0.20) {
        flags.push(RiskFlag::MakerRatioUnavailableOrLow);
    }

    flags
}

fn is_stable_alpha(metrics: &AccountMetrics) -> bool {
    metrics.closed_markets >= 15
        && metrics.trade_count >= 100
        && metrics.total_volume >= dec!(50000)
        && metrics.total_pnl >= dec!(10000)
        && metrics.win_rate >= dec!(0.70)
        && metrics.profit_loss_ratio >= dec!(1.2)
        && metrics.max_single_market_pnl_share < dec!(0.40)
}

fn is_information_edge(metrics: &AccountMetrics) -> bool {
    metrics.closed_markets >= 8
        && metrics.total_volume >= dec!(25000)
        && metrics.total_pnl >= dec!(10000)
        && metrics.win_rate >= dec!(0.80)
        && metrics.max_single_market_pnl_share < dec!(0.60)
}

fn is_market_maker_bot(metrics: &AccountMetrics) -> bool {
    metrics.trade_count >= 1000
        && metrics.closed_markets >= 50
        && metrics.total_volume >= dec!(250000)
        && metrics.total_pnl > dec!(0)
        && metrics.win_rate >= dec!(0.55)
        && metrics.win_rate <= dec!(0.65)
        && metrics.profit_loss_ratio >= dec!(1.0)
        && metrics.maker_ratio >= dec!(0.60)
}

fn is_swing_trader(metrics: &AccountMetrics) -> bool {
    metrics.closed_markets >= 20
        && metrics.total_pnl >= dec!(10000)
        && metrics.win_rate >= dec!(0.55)
        && metrics.win_rate <= dec!(0.75)
        && metrics.profit_loss_ratio >= dec!(2.0)
        && metrics.max_single_market_pnl_share < dec!(0.50)
}

fn is_core_smart_money(metrics: &AccountMetrics) -> bool {
    metrics.trade_count >= 300
        && metrics.closed_markets >= 30
        && metrics.total_volume >= dec!(250000)
        && metrics.total_pnl >= dec!(50000)
        && metrics.win_rate >= dec!(0.65)
        && metrics.profit_loss_ratio >= dec!(1.5)
        && metrics.max_single_market_pnl_share < dec!(0.40)
}

#[cfg(test)]
mod tests {
    use rust_decimal::Decimal;

    use super::*;

    #[test]
    fn identifies_stable_alpha_wallet() {
        let metrics = metrics();
        let profile = classify_profile(&metrics);

        assert_eq!(profile.primary_tag, AccountTag::StableAlphaWallet);
        assert_eq!(
            profile.smart_money_tier,
            SmartMoneyTier::CandidateSmartMoney
        );
    }

    #[test]
    fn excludes_one_shot_whale() {
        let mut metrics = metrics();
        metrics.max_single_market_pnl_share = dec!(0.80);

        let profile = classify_profile(&metrics);

        assert_eq!(profile.primary_tag, AccountTag::OneShotWhale);
        assert_eq!(profile.smart_money_tier, SmartMoneyTier::NotSmartMoney);
    }

    fn metrics() -> AccountMetrics {
        AccountMetrics {
            account: "0xabc".to_string(),
            total_volume: dec!(75000),
            avg_trade_size: dec!(750),
            trade_count: 100,
            distinct_markets: 20,
            closed_markets: 15,
            total_pnl: dec!(15000),
            win_rate: dec!(0.72),
            profit_loss_ratio: dec!(1.3),
            expectancy: dec!(200),
            max_single_market_pnl_share: dec!(0.25),
            maker_ratio: dec!(0.30),
            dominant_sector: None,
            sector_concentration: Decimal::ZERO,
        }
    }
}
