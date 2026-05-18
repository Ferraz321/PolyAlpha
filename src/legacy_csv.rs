use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use oktrader_alpha::ingestion::DataApiClient;
use oktrader_alpha::model::FillEvent;
use serde::Serialize;
use tracing::info;

use crate::cli::{AnalyzeCsvArgs, ScanDataApiArgs};
use crate::processes::fetch_data_api_fills;
use crate::report::{build_reports, filter_reports};

#[derive(Debug, Serialize)]
struct ScannerStats {
    scanned_at: DateTime<Utc>,
    new_trades: usize,
    new_wallets: usize,
    total_trades: usize,
    total_unique_wallets: usize,
    report_accounts: usize,
    passed_funnel_accounts: usize,
    matched_accounts: usize,
    fills_path: String,
    report_path: String,
    matches_path: String,
}

pub fn analyze_csv(args: AnalyzeCsvArgs) -> Result<()> {
    let mut reader = csv::Reader::from_path(args.input)?;
    let fills = reader
        .deserialize::<FillEvent>()
        .collect::<Result<Vec<_>, csv::Error>>()?;
    let reports = build_reports(fills, args.passed_only, args.close_loop_alpha)?;
    let filters = args.filters.clone().load()?;
    let reports = filter_reports(&reports, &filters);

    println!("{}", serde_json::to_string_pretty(&reports)?);
    Ok(())
}

pub async fn scan_data_api(args: ScanDataApiArgs) -> Result<()> {
    ensure_parent(&args.out_fills)?;
    ensure_parent(&args.out_report)?;
    ensure_parent(&args.out_matches)?;
    ensure_parent(&args.out_stats)?;
    let client = DataApiClient::new(&args.data_api_base_url)?;
    let filters = args.filters.clone().load()?;

    loop {
        let cycle = scan_once(&client, &args).await?;
        let fills = read_fills(&args.out_fills)?;
        let total_trades = fills.len();
        let total_unique_wallets = unique_wallets(&fills).len();
        let reports = build_reports(fills, args.passed_only, args.close_loop_alpha)?;
        let passed = reports.iter().filter(|report| report.passed_funnel).count();
        let matched = filter_reports(&reports, &filters);

        fs::write(&args.out_report, serde_json::to_vec_pretty(&reports)?)?;
        fs::write(&args.out_matches, serde_json::to_vec_pretty(&matched)?)?;
        write_stats(
            &args,
            cycle,
            total_trades,
            total_unique_wallets,
            reports.len(),
            passed,
            matched.len(),
        )?;

        info!(
            new_trades = cycle.0,
            new_wallets = cycle.1,
            "csv scan cycle complete"
        );
        println!(
            "scan complete: new_trades={}, new_wallets={}, total_wallets={}, passed={}, matched={}",
            cycle.0,
            cycle.1,
            total_unique_wallets,
            passed,
            matched.len()
        );
        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

async fn scan_once(client: &DataApiClient, args: &ScanDataApiArgs) -> Result<(usize, usize)> {
    let mut seen = read_existing_keys(&args.out_fills)?;
    let mut wallets = unique_wallets(&read_fills(&args.out_fills)?);
    let append_headers = !args.out_fills.exists();
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&args.out_fills)?;
    let mut writer = csv::WriterBuilder::new()
        .has_headers(append_headers)
        .from_writer(file);
    let mut new_trades = 0usize;
    let mut new_wallets = 0usize;

    for fill in fetch_data_api_fills(client, args.page_size, args.max_offset).await? {
        let key = stable_key(&fill);
        if seen.contains(&key) {
            continue;
        }
        if wallets.insert(fill.account.clone()) {
            new_wallets += 1;
        }
        writer.serialize(fill)?;
        seen.insert(key);
        new_trades += 1;
    }

    writer.flush()?;
    Ok((new_trades, new_wallets))
}

fn read_fills(input: &PathBuf) -> Result<Vec<FillEvent>> {
    if !input.exists() {
        return Ok(Vec::new());
    }
    let mut reader = csv::Reader::from_path(input)?;
    reader
        .deserialize::<FillEvent>()
        .collect::<Result<Vec<_>, csv::Error>>()
        .context("failed to read normalized fills csv")
}

fn read_existing_keys(input: &PathBuf) -> Result<HashSet<String>> {
    Ok(read_fills(input)?
        .into_iter()
        .map(|fill| stable_key(&fill))
        .collect())
}

fn unique_wallets(fills: &[FillEvent]) -> HashSet<String> {
    fills.iter().map(|fill| fill.account.clone()).collect()
}

fn stable_key(fill: &FillEvent) -> String {
    format!(
        "{}:{}:{}:{}:{}:{}",
        fill.tx_hash.as_deref().unwrap_or(""),
        fill.account,
        fill.condition_id.as_deref().unwrap_or(""),
        fill.market_id,
        fill.side,
        fill.timestamp.timestamp()
    )
}

fn ensure_parent(path: &std::path::Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    Ok(())
}

fn write_stats(
    args: &ScanDataApiArgs,
    cycle: (usize, usize),
    total_trades: usize,
    total_unique_wallets: usize,
    report_accounts: usize,
    passed_funnel_accounts: usize,
    matched_accounts: usize,
) -> Result<()> {
    let stats = ScannerStats {
        scanned_at: Utc::now(),
        new_trades: cycle.0,
        new_wallets: cycle.1,
        total_trades,
        total_unique_wallets,
        report_accounts,
        passed_funnel_accounts,
        matched_accounts,
        fills_path: args.out_fills.display().to_string(),
        report_path: args.out_report.display().to_string(),
        matches_path: args.out_matches.display().to_string(),
    };
    fs::write(&args.out_stats, serde_json::to_vec_pretty(&stats)?)?;
    Ok(())
}
