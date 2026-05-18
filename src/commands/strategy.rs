use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_research::StrategyRecord;
use oktrader_alpha::strategy_config::{StrategyConfig, parse_strategy_config};

use crate::app::cli::ValidateStrategyConfigArgs;

pub fn validate_config(args: ValidateStrategyConfigArgs) -> Result<()> {
    let content = fs::read_to_string(&args.input)
        .with_context(|| format!("failed to read {}", args.input.display()))?;
    let config = parse_strategy_config(&content)?;
    let enabled = config
        .strategies
        .iter()
        .filter(|strategy| strategy.enabled)
        .count();
    println!(
        "strategy_config: version={}, strategies={}, enabled={}",
        config.version,
        config.strategies.len(),
        enabled
    );
    if let Some(db) = args.db {
        let storage = Storage::open(db)?;
        upsert_strategies(&storage, &config)?;
        println!(
            "strategy_config: persisted_strategies={}",
            config.strategies.len()
        );
    }
    Ok(())
}

pub fn upsert_strategies(storage: &Storage, config: &StrategyConfig) -> Result<()> {
    for strategy in &config.strategies {
        storage.upsert_strategy_record(&StrategyRecord {
            strategy_id: strategy.id.clone(),
            name: strategy.id.clone(),
            lifecycle_state: if strategy.enabled {
                "live".to_string()
            } else {
                "draft".to_string()
            },
            config_json: serde_json::to_string(strategy)?,
            source_factors_json: serde_json::to_string(
                &strategy
                    .trigger
                    .all
                    .iter()
                    .map(|condition| condition.feature.clone())
                    .collect::<Vec<_>>(),
            )?,
            risk_json: serde_json::to_string(&strategy.risk)?,
        })?;
    }
    Ok(())
}
