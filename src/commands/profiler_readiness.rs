use std::collections::HashSet;
use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::metrics::{MetricsConfig, compute_account_metrics};
use oktrader_alpha::storage::Storage;
use rust_decimal_macros::dec;
use serde::Serialize;

use crate::app::cli::ProfileReadinessArgs;

#[derive(Serialize)]
struct ReadinessReport {
    account: String,
    ready: bool,
    trade_count: usize,
    distinct_markets: usize,
    closed_markets: usize,
    clob_aligned_fills: usize,
    total_pnl: String,
    win_rate: String,
    reasons: Vec<String>,
}

pub fn profile_readiness(args: ProfileReadinessArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    let wallets = read_wallet_pool(&args.wallet_pool)?;
    let mut reports = Vec::new();
    for wallet in wallets {
        reports.push(check_wallet(&storage, &wallet, &args)?);
    }
    println!("{}", serde_json::to_string_pretty(&reports)?);
    Ok(())
}

fn check_wallet(
    storage: &Storage,
    wallet: &str,
    args: &ProfileReadinessArgs,
) -> Result<ReadinessReport> {
    let fills = storage.load_fills_for_wallets(&[wallet.to_string()])?;
    let (metrics, _) = compute_account_metrics(
        &fills,
        MetricsConfig {
            close_loop_alpha: dec!(0.95),
        },
    )?;
    let metric = metrics.into_iter().next();
    let clob_aligned = clob_aligned_count(storage, &fills, args.clob_lookback_secs)?;
    let mut reasons = Vec::new();
    let trade_count = metric.as_ref().map(|m| m.trade_count).unwrap_or(0);
    let distinct_markets = metric.as_ref().map(|m| m.distinct_markets).unwrap_or(0);
    let closed_markets = metric.as_ref().map(|m| m.closed_markets).unwrap_or(0);

    if trade_count < args.min_trades {
        reasons.push(format!("trades {trade_count} < {}", args.min_trades));
    }
    if distinct_markets < args.min_markets {
        reasons.push(format!(
            "distinct_markets {distinct_markets} < {}",
            args.min_markets
        ));
    }
    if closed_markets < args.min_closed_markets {
        reasons.push(format!(
            "closed_markets {closed_markets} < {}",
            args.min_closed_markets
        ));
    }
    if clob_aligned < args.min_clob_aligned {
        reasons.push(format!(
            "clob_aligned_fills {clob_aligned} < {}",
            args.min_clob_aligned
        ));
    }

    Ok(ReadinessReport {
        account: wallet.to_string(),
        ready: reasons.is_empty(),
        trade_count,
        distinct_markets,
        closed_markets,
        clob_aligned_fills: clob_aligned,
        total_pnl: metric
            .as_ref()
            .map(|m| m.total_pnl.to_string())
            .unwrap_or_else(|| "0".to_string()),
        win_rate: metric
            .as_ref()
            .map(|m| m.win_rate.to_string())
            .unwrap_or_else(|| "0".to_string()),
        reasons,
    })
}

fn clob_aligned_count(
    storage: &Storage,
    fills: &[oktrader_alpha::model::FillEvent],
    lookback_secs: i64,
) -> Result<usize> {
    let mut count = 0usize;
    for fill in fills {
        if !storage
            .clob_events_around_fill(&fill.market_id, fill.timestamp, lookback_secs, 0, 1)?
            .is_empty()
        {
            count += 1;
        }
    }
    Ok(count)
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
