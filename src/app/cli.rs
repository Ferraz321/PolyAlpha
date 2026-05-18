use std::path::PathBuf;

use clap::{Args, Parser, Subcommand};
use oktrader_alpha::tagging::{AccountTag, SmartMoneyTier};

#[derive(Debug, Parser)]
#[command(version, about = "Cross-market Polymarket smart-money mining toolkit")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    InitDb(DbArgs),
    CollectorDataApi(CollectorDataApiArgs),
    Analyzer(AnalyzerArgs),
    Monitor(MonitorArgs),
    Summary(DbArgs),
    Export(ExportArgs),
    SyncMetadata(SyncMetadataArgs),
    AnalyzeCsv(AnalyzeCsvArgs),
    ScanDataApi(ScanDataApiArgs),
    ListTaxonomy,
    BackfillPolygon(BackfillPolygonArgs),
    WatchLive(WatchLiveArgs),
    WatchClob(WatchClobArgs),
    BuildMicrostructure(BuildMicrostructureArgs),
}

#[derive(Debug, Clone, Args)]
pub struct DbArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
}

#[derive(Debug, Clone, Args)]
pub struct CollectorDataApiArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value = "https://data-api.polymarket.com/")]
    pub data_api_base_url: String,
    #[arg(long, default_value_t = 1000)]
    pub page_size: usize,
    #[arg(long, default_value_t = 10000)]
    pub max_offset: usize,
    #[arg(long, default_value_t = 30)]
    pub interval_secs: u64,
    #[arg(long)]
    pub once: bool,
}

#[derive(Debug, Clone, Args)]
pub struct AnalyzerArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value = "data/matched_accounts.json")]
    pub out_matches: PathBuf,
    #[arg(long, default_value = "data/account_reports.json")]
    pub out_report: PathBuf,
    #[arg(long, default_value_t = 60)]
    pub interval_secs: u64,
    #[arg(long)]
    pub once: bool,
    #[arg(long, default_value = "0.95")]
    pub close_loop_alpha: rust_decimal::Decimal,
    #[command(flatten)]
    pub filters: ReportFilterArgs,
}

#[derive(Debug, Clone, Args)]
pub struct MonitorArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value_t = 10)]
    pub interval_secs: u64,
    #[arg(long)]
    pub once: bool,
}

#[derive(Debug, Clone, Args)]
pub struct ExportArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value = "data/matched_accounts.json")]
    pub out: PathBuf,
}

#[derive(Debug, Clone, Args)]
pub struct SyncMetadataArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value = "https://gamma-api.polymarket.com/")]
    pub gamma_base_url: String,
    #[arg(long, default_value_t = 500)]
    pub limit: usize,
    #[arg(long, default_value_t = 10000)]
    pub max_offset: usize,
}

#[derive(Debug, Clone, Args)]
pub struct AnalyzeCsvArgs {
    #[arg(long)]
    pub input: PathBuf,
    #[arg(long)]
    pub passed_only: bool,
    #[arg(long, default_value = "0.95")]
    pub close_loop_alpha: rust_decimal::Decimal,
    #[command(flatten)]
    pub filters: ReportFilterArgs,
}

#[derive(Debug, Clone, Args)]
pub struct ScanDataApiArgs {
    #[arg(long, default_value = "data/fills.csv")]
    pub out_fills: PathBuf,
    #[arg(long, default_value = "data/account_reports.json")]
    pub out_report: PathBuf,
    #[arg(long, default_value = "data/matched_accounts.json")]
    pub out_matches: PathBuf,
    #[arg(long, default_value = "data/scanner_stats.json")]
    pub out_stats: PathBuf,
    #[arg(long, default_value = "https://data-api.polymarket.com/")]
    pub data_api_base_url: String,
    #[arg(long, default_value_t = 1000)]
    pub page_size: usize,
    #[arg(long, default_value_t = 10000)]
    pub max_offset: usize,
    #[arg(long, default_value_t = 60)]
    pub interval_secs: u64,
    #[arg(long)]
    pub once: bool,
    #[arg(long)]
    pub passed_only: bool,
    #[arg(long, default_value = "0.95")]
    pub close_loop_alpha: rust_decimal::Decimal,
    #[command(flatten)]
    pub filters: ReportFilterArgs,
}

#[derive(Debug, Clone, Args)]
pub struct BackfillPolygonArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long)]
    pub rpc_url: String,
    #[arg(long, default_value = "0xE111180000d2663C0091e4f400237545B87B996B")]
    pub ctf_exchange: String,
    #[arg(long = "exchange")]
    pub exchanges: Vec<String>,
    #[arg(long)]
    pub include_neg_risk: bool,
    #[arg(long)]
    pub from_block: u64,
    #[arg(long, default_value = "latest")]
    pub to_block: String,
    #[arg(long, default_value_t = 5000)]
    pub batch_blocks: u64,
    #[arg(long)]
    pub once: bool,
}

#[derive(Debug, Clone, Args)]
pub struct WatchLiveArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long)]
    pub rpc_url: String,
    #[arg(long, default_value = "0xE111180000d2663C0091e4f400237545B87B996B")]
    pub ctf_exchange: String,
    #[arg(long = "exchange")]
    pub exchanges: Vec<String>,
    #[arg(long)]
    pub include_neg_risk: bool,
    #[arg(long, default_value_t = 15)]
    pub interval_secs: u64,
    #[arg(long, default_value_t = 25)]
    pub lookback_blocks: u64,
    #[arg(long, default_value_t = 2000)]
    pub max_blocks_per_cycle: u64,
    #[arg(long)]
    pub once: bool,
}

#[derive(Debug, Clone, Args)]
pub struct WatchClobArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(
        long,
        default_value = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    )]
    pub ws_url: String,
    #[arg(long)]
    pub assets_file: PathBuf,
    #[arg(long, default_value_t = 500)]
    pub chunk_size: usize,
    #[arg(long, default_value_t = 10)]
    pub ping_secs: u64,
    #[arg(long, default_value_t = 2)]
    pub reconnect_min_secs: u64,
    #[arg(long, default_value_t = 60)]
    pub reconnect_max_secs: u64,
    #[arg(long)]
    pub once: bool,
}

#[derive(Debug, Clone, Args)]
pub struct BuildMicrostructureArgs {
    #[arg(long, default_value = "data/oktrader.sqlite")]
    pub db: PathBuf,
    #[arg(long, default_value_t = 60)]
    pub pre_secs: i64,
    #[arg(long, default_value_t = 30)]
    pub post_secs: i64,
    #[arg(long, default_value_t = 25)]
    pub event_limit: usize,
}

#[derive(Debug, Clone, Args)]
pub struct ReportFilterArgs {
    #[arg(long = "tier", value_enum)]
    pub tiers: Vec<SmartMoneyTier>,
    #[arg(long = "tag", value_enum)]
    pub tags: Vec<AccountTag>,
    #[arg(long)]
    pub wallet_pool: Option<PathBuf>,
}
