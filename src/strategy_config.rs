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

#[derive(Debug, Clone, Default)]
pub struct FeatureSnapshot {
    pub ofi: Option<f64>,
    pub spread: Option<f64>,
    pub price_momentum: Option<f64>,
    pub depth_imbalance: Option<f64>,
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
                "ofi" | "spread" | "price_momentum" | "depth_imbalance"
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

pub fn matching_strategy_ids(config: &StrategyConfig, snapshot: &FeatureSnapshot) -> Vec<String> {
    config
        .strategies
        .iter()
        .filter(|strategy| strategy.enabled)
        .filter(|strategy| {
            strategy
                .trigger
                .all
                .iter()
                .all(|condition| condition_matches(condition, snapshot))
        })
        .map(|strategy| strategy.id.clone())
        .collect()
}

fn condition_matches(condition: &Condition, snapshot: &FeatureSnapshot) -> bool {
    let Some(value) = feature_value(&condition.feature, snapshot) else {
        return false;
    };
    match condition.op.as_str() {
        ">" => value > condition.value,
        ">=" => value >= condition.value,
        "<" => value < condition.value,
        "<=" => value <= condition.value,
        "==" => (value - condition.value).abs() < f64::EPSILON,
        _ => false,
    }
}

fn feature_value(feature: &str, snapshot: &FeatureSnapshot) -> Option<f64> {
    match feature {
        "ofi" => snapshot.ofi,
        "spread" => snapshot.spread,
        "price_momentum" => snapshot.price_momentum,
        "depth_imbalance" => snapshot.depth_imbalance,
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::{FeatureSnapshot, matching_strategy_ids, parse_strategy_config};

    #[test]
    fn validates_and_matches_depth_aware_strategy() {
        let config = parse_strategy_config(
            r#"{
              "version": 1,
              "strategies": [{
                "id": "reverse_test",
                "source_wallet": "0xabc",
                "enabled": true,
                "trigger": {"all": [
                  {"feature": "ofi", "op": ">", "value": 0.5},
                  {"feature": "depth_imbalance", "op": ">=", "value": 0.1}
                ]},
                "risk": {"mode": "alert_only", "max_notional_usd": 0}
              }]
            }"#,
        )
        .unwrap();
        let snapshot = FeatureSnapshot {
            ofi: Some(0.7),
            depth_imbalance: Some(0.2),
            ..Default::default()
        };
        assert_eq!(
            matching_strategy_ids(&config, &snapshot),
            vec!["reverse_test"]
        );
    }
}
