use std::collections::HashSet;
use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::storage::Storage;

use crate::app::cli::ExportProfilerArgs;

pub fn export_profiler(args: ExportProfilerArgs) -> Result<()> {
    ensure_parent(&args.out_fills)?;
    ensure_parent(&args.out_clob)?;
    let wallets = read_wallet_pool(&args.wallet_pool)?;
    let storage = Storage::open(&args.db)?;
    export_fills(&storage, &wallets, &args.out_fills)?;
    export_clob(&storage, &args.out_clob)?;
    println!(
        "profiler_export: wallets={}, fills={}, clob={}",
        wallets.len(),
        args.out_fills.display(),
        args.out_clob.display()
    );
    Ok(())
}

fn export_fills(storage: &Storage, wallets: &HashSet<String>, out: &std::path::Path) -> Result<()> {
    let mut writer = csv::Writer::from_path(out)?;
    writer.write_record([
        "account",
        "market_id",
        "condition_id",
        "event_slug",
        "sector",
        "side",
        "role",
        "price",
        "shares",
        "timestamp",
        "tx_hash",
        "order_hash",
    ])?;
    for fill in storage.load_fills()? {
        if wallets.contains(&fill.account.to_ascii_lowercase()) {
            writer.serialize(fill)?;
        }
    }
    writer.flush()?;
    Ok(())
}

fn export_clob(storage: &Storage, out: &std::path::Path) -> Result<()> {
    let mut writer = csv::Writer::from_path(out)?;
    writer.write_record(["asset_id", "received_at", "event_type", "payload"])?;
    for row in storage.load_profiler_clob_rows()? {
        writer.serialize(row)?;
    }
    writer.flush()?;
    Ok(())
}

fn read_wallet_pool(path: &std::path::Path) -> Result<HashSet<String>> {
    Ok(fs::read_to_string(path)
        .with_context(|| format!("failed to read {}", path.display()))?
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .filter_map(|line| line.split(',').next())
        .map(|wallet| wallet.trim().to_ascii_lowercase())
        .collect())
}

fn ensure_parent(path: &std::path::Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).context("failed to create profiler export dir")?;
    }
    Ok(())
}
