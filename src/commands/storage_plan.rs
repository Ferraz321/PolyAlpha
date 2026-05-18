use anyhow::{Context, Result};
use serde_json::Value;
use std::fs;

use crate::app::cli::StoragePlanArgs;

pub fn storage_plan(args: StoragePlanArgs) -> Result<()> {
    let content = fs::read_to_string(&args.config)
        .with_context(|| format!("failed to read {}", args.config.display()))?;
    let value: Value = serde_json::from_str(&content).context("invalid storage backend config")?;
    println!("storage_plan: config={}", args.config.display());
    println!(
        "default={}",
        value
            .get("default")
            .and_then(Value::as_str)
            .unwrap_or("sqlite_local")
    );
    if let Some(backends) = value.get("backends").and_then(Value::as_object) {
        for (name, backend) in backends {
            let kind = backend
                .get("kind")
                .and_then(Value::as_str)
                .unwrap_or("unknown");
            let purpose = backend
                .get("purpose")
                .and_then(Value::as_str)
                .unwrap_or("-");
            let dsn_env = backend
                .get("dsn_env")
                .and_then(Value::as_str)
                .unwrap_or("-");
            let schema = backend.get("schema").and_then(Value::as_str).unwrap_or("-");
            println!("{name}: kind={kind} dsn_env={dsn_env} schema={schema} purpose={purpose}");
        }
    }
    Ok(())
}
