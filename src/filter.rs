use rust_decimal::Decimal;
use rust_decimal_macros::dec;

use crate::model::AccountMetrics;

#[derive(Debug, Clone)]
pub struct FunnelConfig {
    pub min_total_volume: Decimal,
    pub min_avg_trade_size: Decimal,
    pub min_closed_markets: usize,
    pub min_total_pnl: Decimal,
    pub min_win_rate: Decimal,
}

impl Default for FunnelConfig {
    fn default() -> Self {
        Self {
            min_total_volume: dec!(50000),
            min_avg_trade_size: dec!(1000),
            min_closed_markets: 15,
            min_total_pnl: dec!(10000),
            min_win_rate: dec!(0.75),
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct FunnelDecision {
    pub account: String,
    pub passed: bool,
    pub failed_reasons: Vec<String>,
}

pub fn evaluate(metrics: &AccountMetrics, config: &FunnelConfig) -> FunnelDecision {
    let mut failed_reasons = Vec::new();

    if metrics.total_volume < config.min_total_volume {
        failed_reasons.push("capacity.total_volume".to_string());
    }
    if metrics.avg_trade_size < config.min_avg_trade_size {
        failed_reasons.push("capacity.avg_trade_size".to_string());
    }
    if metrics.closed_markets < config.min_closed_markets {
        failed_reasons.push("significance.closed_markets".to_string());
    }
    if metrics.total_pnl < config.min_total_pnl {
        failed_reasons.push("alpha.total_pnl".to_string());
    }
    if metrics.win_rate < config.min_win_rate {
        failed_reasons.push("alpha.win_rate".to_string());
    }

    FunnelDecision {
        account: metrics.account.clone(),
        passed: failed_reasons.is_empty(),
        failed_reasons,
    }
}
