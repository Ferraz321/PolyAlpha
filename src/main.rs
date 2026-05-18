use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use clap::{Args, Parser, Subcommand};
use oktrader_alpha::filter::{FunnelConfig, evaluate};
use oktrader_alpha::ingestion::DataApiClient;
use oktrader_alpha::metrics::{MetricsConfig, compute_account_metrics};
use oktrader_alpha::model::FillEvent;
use oktrader_alpha::storage::{Storage, metric_parts};
use oktrader_alpha::tagging::{
    AccountClassification, AccountTag, SmartMoneyTier, classify_profile,
};
use serde::Serialize;
use tracing::info;
use tracing_subscriber::EnvFilter;

#[derive(Debug, Parser)]
#[command(version, about = "Cross-market Polymarket smart-money mining toolkit")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    /// Initialize the SQLite database schema.
    InitDb {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,
    },

    /// Collector process: continuously pull public Polymarket Data API trades into SQLite.
    CollectorDataApi {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,

        /// Data API base URL.
        #[arg(long, default_value = "https://data-api.polymarket.com/")]
        data_api_base_url: String,

        /// Page size for /trades.
        #[arg(long, default_value_t = 1000)]
        page_size: usize,

        /// Maximum offset to scan per cycle. Data API currently documents offsets up to 10000.
        #[arg(long, default_value_t = 10000)]
        max_offset: usize,

        /// Seconds between scan cycles.
        #[arg(long, default_value_t = 30)]
        interval_secs: u64,

        /// Run one cycle and exit.
        #[arg(long)]
        once: bool,
    },

    /// Analyzer process: continuously classify wallets from SQLite fills.
    Analyzer {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,

        /// Filtered matched accounts JSON written after every analysis cycle.
        #[arg(long, default_value = "data/matched_accounts.json")]
        out_matches: PathBuf,

        /// Account report JSON written after every analysis cycle.
        #[arg(long, default_value = "data/account_reports.json")]
        out_report: PathBuf,

        /// Seconds between analysis cycles.
        #[arg(long, default_value_t = 60)]
        interval_secs: u64,

        /// Run one cycle and exit.
        #[arg(long)]
        once: bool,

        /// Closed-loop threshold. 0.95 means sells must cover at least 95% of buys.
        #[arg(long, default_value = "0.95")]
        close_loop_alpha: rust_decimal::Decimal,

        #[command(flatten)]
        filters: ReportFilterArgs,
    },

    /// Monitor process: continuously print currently matched smart-money wallets.
    Monitor {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,

        /// Seconds between monitor cycles.
        #[arg(long, default_value_t = 10)]
        interval_secs: u64,

        /// Run one cycle and exit.
        #[arg(long)]
        once: bool,
    },

    /// Export matched accounts or all reports from SQLite.
    Export {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,

        /// Output JSON file.
        #[arg(long, default_value = "data/matched_accounts.json")]
        out: PathBuf,
    },

    /// Compute account feature vectors and funnel decisions from normalized fills CSV.
    AnalyzeCsv {
        /// Input CSV with normalized fill events.
        #[arg(long)]
        input: PathBuf,

        /// Emit only accounts passing the smart-money funnel.
        #[arg(long)]
        passed_only: bool,

        /// Closed-loop threshold. 0.95 means sells must cover at least 95% of buys.
        #[arg(long, default_value = "0.95")]
        close_loop_alpha: rust_decimal::Decimal,

        #[command(flatten)]
        filters: ReportFilterArgs,
    },

    /// Continuously pull public Polymarket Data API trades and refresh account reports.
    ScanDataApi {
        /// Normalized fills CSV written by the scanner.
        #[arg(long, default_value = "data/fills.csv")]
        out_fills: PathBuf,

        /// Account report JSON written after every scan cycle.
        #[arg(long, default_value = "data/account_reports.json")]
        out_report: PathBuf,

        /// Filtered matched accounts JSON written after every scan cycle.
        #[arg(long, default_value = "data/matched_accounts.json")]
        out_matches: PathBuf,

        /// Scanner stats JSON written after every scan cycle.
        #[arg(long, default_value = "data/scanner_stats.json")]
        out_stats: PathBuf,

        /// Data API base URL.
        #[arg(long, default_value = "https://data-api.polymarket.com/")]
        data_api_base_url: String,

        /// Page size for /trades.
        #[arg(long, default_value_t = 1000)]
        page_size: usize,

        /// Maximum offset to scan per cycle. Data API currently documents offsets up to 10000.
        #[arg(long, default_value_t = 10000)]
        max_offset: usize,

        /// Seconds between scan cycles.
        #[arg(long, default_value_t = 60)]
        interval_secs: u64,

        /// Run one cycle and exit.
        #[arg(long)]
        once: bool,

        /// Emit only accounts passing the smart-money funnel in report JSON.
        #[arg(long)]
        passed_only: bool,

        /// Closed-loop threshold. 0.95 means sells must cover at least 95% of buys.
        #[arg(long, default_value = "0.95")]
        close_loop_alpha: rust_decimal::Decimal,

        #[command(flatten)]
        filters: ReportFilterArgs,
    },

    /// Print supported smart-money tiers and account types.
    ListTaxonomy,

    /// Placeholder for historical Polygon OrderFilled replay.
    BackfillPolygon {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,

        /// Polygon RPC URL.
        #[arg(long)]
        rpc_url: String,

        /// Start block.
        #[arg(long)]
        from_block: u64,

        /// End block or latest.
        #[arg(long, default_value = "latest")]
        to_block: String,
    },

    /// Placeholder for live Polygon/CLOB monitoring.
    WatchLive {
        /// SQLite database path.
        #[arg(long, default_value = "data/oktrader.sqlite")]
        db: PathBuf,
    },
}

#[derive(Debug, Clone, Serialize)]
struct AccountReport {
    #[serde(flatten)]
    metrics: oktrader_alpha::model::AccountMetrics,
    passed_funnel: bool,
    failed_reasons: Vec<String>,
    #[serde(flatten)]
    classification: AccountClassification,
}

#[derive(Debug, Clone, Args)]
struct ReportFilterArgs {
    /// Keep only these smart-money tiers. Can be repeated.
    #[arg(long = "tier", value_enum)]
    tiers: Vec<SmartMoneyTier>,

    /// Keep only these account or bot types. Can be repeated.
    #[arg(long = "tag", value_enum)]
    tags: Vec<AccountTag>,

    /// Optional file containing one wallet address per line.
    #[arg(long)]
    wallet_pool: Option<PathBuf>,
}

#[derive(Debug, Clone)]
struct ReportFilter {
    tiers: HashSet<SmartMoneyTier>,
    tags: HashSet<AccountTag>,
    wallet_pool: Option<HashSet<String>>,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    match Cli::parse().command {
        Commands::InitDb { db } => init_db(db),
        Commands::CollectorDataApi {
            db,
            data_api_base_url,
            page_size,
            max_offset,
            interval_secs,
            once,
        } => {
            collector_data_api(DbCollectorOptions {
                db,
                data_api_base_url,
                page_size,
                max_offset,
                interval_secs,
                once,
            })
            .await
        }
        Commands::Analyzer {
            db,
            out_matches,
            out_report,
            interval_secs,
            once,
            close_loop_alpha,
            filters,
        } => {
            analyzer(DbAnalyzerOptions {
                db,
                out_matches,
                out_report,
                interval_secs,
                once,
                close_loop_alpha,
                filters: filters.load()?,
            })
            .await
        }
        Commands::Monitor {
            db,
            interval_secs,
            once,
        } => {
            monitor(DbMonitorOptions {
                db,
                interval_secs,
                once,
            })
            .await
        }
        Commands::Export { db, out } => export_matched(db, out),
        Commands::AnalyzeCsv {
            input,
            passed_only,
            close_loop_alpha,
            filters,
        } => analyze_csv(input, passed_only, close_loop_alpha, filters),
        Commands::ScanDataApi {
            out_fills,
            out_report,
            out_matches,
            out_stats,
            data_api_base_url,
            page_size,
            max_offset,
            interval_secs,
            once,
            passed_only,
            close_loop_alpha,
            filters,
        } => {
            let options = ScanOptions {
                out_fills,
                out_report,
                out_matches,
                out_stats,
                data_api_base_url,
                page_size,
                max_offset,
                interval_secs,
                once,
                passed_only,
                close_loop_alpha,
                filters: filters.load()?,
            };
            scan_data_api(options).await
        }
        Commands::ListTaxonomy => {
            print_taxonomy();
            Ok(())
        }
        Commands::BackfillPolygon {
            db,
            rpc_url,
            from_block,
            to_block,
        } => backfill_polygon(db, rpc_url, from_block, to_block),
        Commands::WatchLive { db } => watch_live(db),
    }
}

fn init_db(db: PathBuf) -> Result<()> {
    let storage = Storage::open(&db)?;
    storage.init()?;
    println!("initialized sqlite database: {}", db.display());
    Ok(())
}

#[derive(Debug)]
struct DbCollectorOptions {
    db: PathBuf,
    data_api_base_url: String,
    page_size: usize,
    max_offset: usize,
    interval_secs: u64,
    once: bool,
}

#[derive(Debug)]
struct DbAnalyzerOptions {
    db: PathBuf,
    out_matches: PathBuf,
    out_report: PathBuf,
    interval_secs: u64,
    once: bool,
    close_loop_alpha: rust_decimal::Decimal,
    filters: ReportFilter,
}

#[derive(Debug)]
struct DbMonitorOptions {
    db: PathBuf,
    interval_secs: u64,
    once: bool,
}

async fn collector_data_api(options: DbCollectorOptions) -> Result<()> {
    let client = DataApiClient::new(&options.data_api_base_url)?;
    let mut storage = Storage::open(&options.db)?;
    storage.init()?;

    loop {
        let fills = fetch_data_api_fills(&client, options.page_size, options.max_offset).await?;
        let summary = storage.insert_fills(&fills)?;
        let stats = storage.stats()?;
        println!(
            "collector: inserted_fills={}, new_wallets={}, total_fills={}, total_wallets={}",
            summary.inserted_fills, summary.new_wallets, stats.fills, stats.wallets
        );

        if options.once {
            break;
        }

        tokio::time::sleep(Duration::from_secs(options.interval_secs)).await;
    }

    Ok(())
}

async fn fetch_data_api_fills(
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

async fn analyzer(options: DbAnalyzerOptions) -> Result<()> {
    if let Some(parent) = options.out_matches.parent() {
        fs::create_dir_all(parent).context("failed to create matches output directory")?;
    }
    if let Some(parent) = options.out_report.parent() {
        fs::create_dir_all(parent).context("failed to create report output directory")?;
    }

    loop {
        let mut storage = Storage::open(&options.db)?;
        let fills = storage.load_fills()?;
        let reports = build_reports(fills, false, options.close_loop_alpha)?;
        let matched_reports = filter_reports(&reports, &options.filters);

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

        fs::write(&options.out_report, serde_json::to_vec_pretty(&reports)?)
            .context("failed to write account report")?;
        fs::write(
            &options.out_matches,
            serde_json::to_vec_pretty(&matched_reports)?,
        )
        .context("failed to write matched accounts")?;

        let stats = storage.stats()?;
        println!(
            "analyzer: wallets={}, reports={}, matched={}, out={}",
            stats.wallets,
            reports.len(),
            matched_reports.len(),
            options.out_matches.display()
        );

        if options.once {
            break;
        }

        tokio::time::sleep(Duration::from_secs(options.interval_secs)).await;
    }

    Ok(())
}

async fn monitor(options: DbMonitorOptions) -> Result<()> {
    loop {
        let storage = Storage::open(&options.db)?;
        let matched = storage.matched_account_json()?;
        println!("monitor: matched_accounts={}", matched.len());
        for report_json in matched.iter().take(10) {
            println!("{report_json}");
        }

        if options.once {
            break;
        }

        tokio::time::sleep(Duration::from_secs(options.interval_secs)).await;
    }

    Ok(())
}

fn export_matched(db: PathBuf, out: PathBuf) -> Result<()> {
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).context("failed to create export output directory")?;
    }

    let storage = Storage::open(&db)?;
    let matched = storage.matched_account_json()?;
    let values = matched
        .into_iter()
        .map(|json| serde_json::from_str::<serde_json::Value>(&json))
        .collect::<Result<Vec<_>, _>>()?;
    fs::write(&out, serde_json::to_vec_pretty(&values)?)?;
    println!("exported matched accounts: {}", out.display());
    Ok(())
}

fn backfill_polygon(db: PathBuf, rpc_url: String, from_block: u64, to_block: String) -> Result<()> {
    let storage = Storage::open(&db)?;
    storage.init()?;
    println!(
        "backfill-polygon planned: db={}, rpc_url={}, from_block={}, to_block={}. Next implementation step: eth_getLogs batching + CTFExchange OrderFilled decoding.",
        db.display(),
        rpc_url,
        from_block,
        to_block
    );
    Ok(())
}

fn watch_live(db: PathBuf) -> Result<()> {
    let storage = Storage::open(&db)?;
    storage.init()?;
    println!(
        "watch-live planned: db={}. Next implementation step: Polygon new-block subscription + Polymarket CLOB websocket ingestion.",
        db.display()
    );
    Ok(())
}

fn analyze_csv(
    input: PathBuf,
    passed_only: bool,
    close_loop_alpha: rust_decimal::Decimal,
    filters: ReportFilterArgs,
) -> Result<()> {
    let mut reader = csv::Reader::from_path(input)?;
    let fills = reader
        .deserialize::<FillEvent>()
        .collect::<Result<Vec<_>, csv::Error>>()?;

    let reports = build_reports(fills, passed_only, close_loop_alpha)?;
    let filters = filters.load()?;
    let reports = filter_reports(&reports, &filters);

    println!("{}", serde_json::to_string_pretty(&reports)?);
    Ok(())
}

#[derive(Debug)]
struct ScanOptions {
    out_fills: PathBuf,
    out_report: PathBuf,
    out_matches: PathBuf,
    out_stats: PathBuf,
    data_api_base_url: String,
    page_size: usize,
    max_offset: usize,
    interval_secs: u64,
    once: bool,
    passed_only: bool,
    close_loop_alpha: rust_decimal::Decimal,
    filters: ReportFilter,
}

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

#[derive(Debug)]
struct ScanCycle {
    new_trades: usize,
    new_wallets: usize,
}

async fn scan_data_api(options: ScanOptions) -> Result<()> {
    if let Some(parent) = options.out_fills.parent() {
        fs::create_dir_all(parent).context("failed to create fills output directory")?;
    }
    if let Some(parent) = options.out_report.parent() {
        fs::create_dir_all(parent).context("failed to create report output directory")?;
    }
    if let Some(parent) = options.out_matches.parent() {
        fs::create_dir_all(parent).context("failed to create matches output directory")?;
    }
    if let Some(parent) = options.out_stats.parent() {
        fs::create_dir_all(parent).context("failed to create stats output directory")?;
    }

    let client = DataApiClient::new(&options.data_api_base_url)?;

    loop {
        let cycle = scan_once(&client, &options).await?;
        let fills = read_fills(&options.out_fills)?;
        let total_trades = fills.len();
        let total_unique_wallets = unique_wallets(&fills).len();
        let reports = build_reports(fills, options.passed_only, options.close_loop_alpha)?;
        let passed_funnel_accounts = reports.iter().filter(|report| report.passed_funnel).count();
        let matched_reports = filter_reports(&reports, &options.filters);
        fs::write(&options.out_report, serde_json::to_vec_pretty(&reports)?)
            .context("failed to write account report")?;
        fs::write(
            &options.out_matches,
            serde_json::to_vec_pretty(&matched_reports)?,
        )
        .context("failed to write matched accounts")?;
        let stats = ScannerStats {
            scanned_at: Utc::now(),
            new_trades: cycle.new_trades,
            new_wallets: cycle.new_wallets,
            total_trades,
            total_unique_wallets,
            report_accounts: reports.len(),
            passed_funnel_accounts,
            matched_accounts: matched_reports.len(),
            fills_path: options.out_fills.display().to_string(),
            report_path: options.out_report.display().to_string(),
            matches_path: options.out_matches.display().to_string(),
        };
        fs::write(&options.out_stats, serde_json::to_vec_pretty(&stats)?)
            .context("failed to write scanner stats")?;

        info!(
            new_trades = cycle.new_trades,
            new_wallets = cycle.new_wallets,
            total_unique_wallets,
            matched_accounts = matched_reports.len(),
            report = %options.out_report.display(),
            "scan cycle complete"
        );
        println!(
            "scan complete: new_trades={}, new_wallets={}, total_wallets={}, passed={}, matched={}, report={}, matches={}, stats={}",
            cycle.new_trades,
            cycle.new_wallets,
            total_unique_wallets,
            passed_funnel_accounts,
            matched_reports.len(),
            options.out_report.display(),
            options.out_matches.display(),
            options.out_stats.display()
        );

        if options.once {
            break;
        }

        tokio::time::sleep(Duration::from_secs(options.interval_secs)).await;
    }

    Ok(())
}

async fn scan_once(client: &DataApiClient, options: &ScanOptions) -> Result<ScanCycle> {
    let existing_keys = read_existing_keys(&options.out_fills)?;
    let mut wallets = unique_wallets(&read_fills(&options.out_fills)?);
    let append_headers = !options.out_fills.exists();
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&options.out_fills)
        .context("failed to open fills csv for append")?;
    let mut writer = csv::WriterBuilder::new()
        .has_headers(append_headers)
        .from_writer(file);

    let mut seen = existing_keys;
    let mut new_trades = 0usize;
    let mut new_wallets = 0usize;
    let mut offset = 0usize;

    while offset <= options.max_offset {
        let trades = client.fetch_trades(options.page_size, offset).await?;
        if trades.is_empty() {
            break;
        }

        for trade in trades {
            let key = trade.stable_key();
            if seen.contains(&key) {
                continue;
            }

            match trade.into_fill_event() {
                Ok(fill) => {
                    if wallets.insert(fill.account.clone()) {
                        new_wallets += 1;
                    }
                    writer.serialize(fill)?;
                    seen.insert(key);
                    new_trades += 1;
                }
                Err(error) => {
                    tracing::warn!(%error, "skipping malformed trade");
                }
            }
        }

        offset += options.page_size;
    }

    writer.flush()?;
    Ok(ScanCycle {
        new_trades,
        new_wallets,
    })
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
    let fills = read_fills(input)?;
    Ok(fills
        .into_iter()
        .map(|fill| {
            format!(
                "{}:{}:{}:{}:{}:{}",
                fill.tx_hash.as_deref().unwrap_or(""),
                fill.account,
                fill.condition_id.as_deref().unwrap_or(""),
                fill.market_id,
                fill.side,
                fill.timestamp.timestamp()
            )
        })
        .collect())
}

fn unique_wallets(fills: &[FillEvent]) -> HashSet<String> {
    fills.iter().map(|fill| fill.account.clone()).collect()
}

fn build_reports(
    fills: Vec<FillEvent>,
    passed_only: bool,
    close_loop_alpha: rust_decimal::Decimal,
) -> Result<Vec<AccountReport>> {
    let (metrics, _closed_loops) =
        compute_account_metrics(&fills, MetricsConfig { close_loop_alpha })?;
    let config = FunnelConfig::default();

    Ok(metrics
        .into_iter()
        .filter_map(|metrics| {
            let decision = evaluate(&metrics, &config);
            if passed_only && !decision.passed {
                return None;
            }

            Some(AccountReport {
                classification: classify_profile(&metrics),
                metrics,
                passed_funnel: decision.passed,
                failed_reasons: decision.failed_reasons,
            })
        })
        .collect())
}

impl ReportFilterArgs {
    fn load(self) -> Result<ReportFilter> {
        let wallet_pool = match self.wallet_pool {
            Some(path) => Some(read_wallet_pool(&path)?),
            None => None,
        };

        Ok(ReportFilter {
            tiers: self.tiers.into_iter().collect(),
            tags: self.tags.into_iter().collect(),
            wallet_pool,
        })
    }
}

fn read_wallet_pool(path: &PathBuf) -> Result<HashSet<String>> {
    let content = fs::read_to_string(path).context("failed to read wallet pool")?;
    Ok(content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(|line| line.to_ascii_lowercase())
        .collect())
}

fn filter_reports<'a>(
    reports: &'a [AccountReport],
    filters: &ReportFilter,
) -> Vec<&'a AccountReport> {
    reports
        .iter()
        .filter(|report| {
            filters.tiers.is_empty()
                || filters
                    .tiers
                    .contains(&report.classification.smart_money_tier)
        })
        .filter(|report| {
            filters.tags.is_empty() || filters.tags.contains(&report.classification.primary_tag)
        })
        .filter(|report| {
            filters.wallet_pool.as_ref().is_none_or(|wallet_pool| {
                wallet_pool.contains(&report.metrics.account.to_ascii_lowercase())
            })
        })
        .collect()
}

fn print_taxonomy() {
    println!(
        r#"smart_money_tier:
  core_smart_money          strictest tier, high sample, high PnL, diversified edge
  candidate_smart_money     good smart-money candidate, worth tracking
  watchlist                 interesting but has risk flags
  not_smart_money           noise, one-shot, unprofitable, or too early

primary_tag:
  stable_alpha_wallet       preferred target: repeatable positive expectancy
  information_edge_wallet   low-frequency but high-accuracy information edge
  stat_arb_market_maker_bot high-frequency market-making/stat-arb account
  swing_trader              high profit/loss ratio directional trader
  one_shot_whale            profitable but dominated by one market
  small_sample_noise        not enough evidence yet
  high_volume_noise         high volume without realized edge
  unprofitable_trader       negative realized PnL
  unclassified              does not match a defined profile yet"#
    );
}
