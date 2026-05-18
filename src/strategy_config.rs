use anyhow::{Context, Result};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct StrategyConfig {
    pub version: u64,
    #[serde(default)]
    pub strategies: Vec<Strategy>,
}

#[derive(Debug, Deserialize)]
pub struct Strategy {
    pub id: String,
    pub source_wallet: String,
    pub enabled: bool,
    pub trigger: Trigger,
    pub risk: Risk,
}

#[derive(Debug, Deserialize)]
pub struct Trigger {
    #[serde(default)]
    pub all: Vec<Condition>,
}

#[derive(Debug, Deserialize)]
pub struct Condition {
    pub feature: String,
    pub op: String,
    pub value: f64,
}

#[derive(Debug, Deserialize)]
pub struct Risk {
    pub mode: String,
    pub max_notional_usd: f64,
}

pub fn parse_strategy_config(json: &str) -> Result<StrategyConfig> {
    let config: StrategyConfig = serde_json::from_str(json).context("invalid strategy config")?;
    for strategy in &config.strategies {
        validate_strategy(strategy)?;
    }
    Ok(config)
}

fn validate_strategy(strategy: &Strategy) -> Result<()> {
    anyhow::ensure!(!strategy.id.is_empty(), "strategy id is empty");
    anyhow::ensure!(
        strategy.source_wallet.starts_with("0x"),
        "source wallet must be hex address"
    );
    anyhow::ensure!(
        !strategy.trigger.all.is_empty(),
        "trigger has no conditions"
    );
    for condition in &strategy.trigger.all {
        anyhow::ensure!(
            matches!(condition.op.as_str(), ">" | ">=" | "<" | "<=" | "=="),
            "unsupported operator {}",
            condition.op
        );
        anyhow::ensure!(
            matches!(
                condition.feature.as_str(),
                "ofi" | "spread" | "price_momentum"
            ),
            "unsupported feature {}",
            condition.feature
        );
    }
    anyhow::ensure!(
        strategy.risk.mode == "alert_only" || strategy.risk.max_notional_usd >= 0.0,
        "invalid risk settings"
    );
    Ok(())
}
