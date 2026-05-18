use std::fs;
use std::time::Duration;

use anyhow::{Context, Result};
use oktrader_alpha::ingestion::DataApiClient;
use oktrader_alpha::model::FillEvent;
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::metric_parts;

use crate::app::cli::{AnalyzerArgs, CollectorDataApiArgs, ExportArgs, MonitorArgs};
use crate::app::report::{build_reports, filter_reports};

pub fn init_db(db: std::path::PathBuf) -> Result<()> {
    let storage = Storage::open(&db)?;
    storage.init()?;
    println!("initialized sqlite database: {}", db.display());
    Ok(())
}

pub async fn collector_data_api(args: CollectorDataApiArgs) -> Result<()> {
    let client = DataApiClient::new(&args.data_api_base_url)?;
    let mut storage = Storage::open(&args.db)?;
    storage.init()?;

    loop {
        let fills = fetch_data_api_fills(&client, args.page_size, args.max_offset).await?;
        let summary = storage.insert_fills(&fills)?;
        let stats = storage.stats()?;
        println!(
            "collector: inserted_fills={}, new_wallets={}, total_fills={}, total_wallets={}",
            summary.inserted_fills, summary.new_wallets, stats.fills, stats.wallets
        );

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

pub async fn analyzer(args: AnalyzerArgs) -> Result<()> {
    ensure_parent(&args.out_matches)?;
    ensure_parent(&args.out_report)?;
    let filters = args.filters.load()?;

    loop {
        let mut storage = Storage::open(&args.db)?;
        let fills = storage.load_fills()?;
        let reports = build_reports(fills, false, args.close_loop_alpha)?;
        let matched_reports = filter_reports(&reports, &filters);

        storage.replace_account_metrics(&reports, |report| {
            metric_parts(
                &report.metrics,
                &report.classification,
                report.passed_funnel,
                &report.failed_reasons,
            )
        })?;
        storage.replace_matched_accounts(
            &matched_reports,
            |report| &report.metrics.account,
            |report| Ok(serde_json::to_string(report)?),
        )?;

        fs::write(&args.out_report, serde_json::to_vec_pretty(&reports)?)?;
        fs::write(
            &args.out_matches,
            serde_json::to_vec_pretty(&matched_reports)?,
        )?;
        println!(
            "analyzer: wallets={}, reports={}, matched={}, out={}",
            storage.stats()?.wallets,
            reports.len(),
            matched_reports.len(),
            args.out_matches.display()
        );

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

pub async fn monitor(args: MonitorArgs) -> Result<()> {
    loop {
        let storage = Storage::open(&args.db)?;
        let matched = storage.matched_account_json()?;
        println!("monitor: matched_accounts={}", matched.len());
        for report_json in matched.iter().take(10) {
            println!("{report_json}");
        }

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }
    Ok(())
}

pub fn export_matched(args: ExportArgs) -> Result<()> {
    ensure_parent(&args.out)?;
    let storage = Storage::open(&args.db)?;
    let values = storage
        .matched_account_json()?
        .into_iter()
        .map(|json| serde_json::from_str::<serde_json::Value>(&json))
        .collect::<Result<Vec<_>, _>>()?;
    fs::write(&args.out, serde_json::to_vec_pretty(&values)?)?;
    println!("exported matched accounts: {}", args.out.display());
    Ok(())
}

pub async fn fetch_data_api_fills(
    client: &DataApiClient,
    page_size: usize,
    max_offset: usize,
) -> Result<Vec<FillEvent>> {
    let mut fills = Vec::new();
    let mut offset = 0usize;

    while offset <= max_offset {
        let trades = client.fetch_trades(page_size, offset).await?;
        if trades.is_empty() {
            break;
        }
        for trade in trades {
            match trade.into_fill_event() {
                Ok(fill) => fills.push(fill),
                Err(error) => tracing::warn!(%error, "skipping malformed trade"),
            }
        }
        offset += page_size;
    }

    Ok(fills)
}

fn ensure_parent(path: &std::path::Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).context("failed to create output directory")?;
    }
    Ok(())
}
