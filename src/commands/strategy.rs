use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::strategy_config::parse_strategy_config;

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
    Ok(())
}
