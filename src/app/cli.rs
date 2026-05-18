use clap::{Parser, Subcommand};

pub use crate::app::cli_args::*;

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
    Alerts(AlertArgs),
    ImportWatchlist(ImportWatchlistArgs),
    ExportProfiler(ExportProfilerArgs),
    ProfileReadiness(ProfileReadinessArgs),
    ValidateStrategyConfig(ValidateStrategyConfigArgs),
    ResearchStatus(DbArgs),
    BuildWalletIntelligence(DbArgs),
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
    ImportSettlements(ImportSettlementsArgs),
    StoragePlan(StoragePlanArgs),
}
