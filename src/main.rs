mod app;
mod chain;
mod commands;

use anyhow::Result;
use app::cli::{Cli, Commands};
use clap::Parser;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    match Cli::parse().command {
        Commands::InitDb(args) => commands::processes::init_db(args.db),
        Commands::CollectorDataApi(args) => commands::processes::collector_data_api(args).await,
        Commands::Analyzer(args) => commands::processes::analyzer(args).await,
        Commands::Monitor(args) => commands::processes::monitor(args).await,
        Commands::Alerts(args) => commands::alerts::alerts(args).await,
        Commands::ImportWatchlist(args) => commands::watchlist::import_watchlist(args),
        Commands::ExportProfiler(args) => commands::profiler_export::export_profiler(args),
        Commands::ProfileReadiness(args) => commands::profiler_readiness::profile_readiness(args),
        Commands::ValidateStrategyConfig(args) => commands::strategy::validate_config(args),
        Commands::ResearchStatus(args) => commands::research_status::research_status(args),
        Commands::BuildWalletIntelligence(args) => {
            commands::wallet_intelligence::build_wallet_intelligence_command(args)
        }
        Commands::Summary(args) => commands::processes::summary(args.db),
        Commands::Export(args) => commands::processes::export_matched(args),
        Commands::SyncMetadata(args) => commands::metadata::sync_metadata(args).await,
        Commands::AnalyzeCsv(args) => commands::legacy_csv::analyze_csv(args),
        Commands::ScanDataApi(args) => commands::legacy_csv::scan_data_api(args).await,
        Commands::ListTaxonomy => {
            app::taxonomy::print_taxonomy();
            Ok(())
        }
        Commands::BackfillPolygon(args) => commands::backfill::backfill_polygon(args).await,
        Commands::WatchLive(args) => commands::planned::watch_live(args).await,
        Commands::WatchClob(args) => commands::clob_ws::watch_clob(args).await,
        Commands::BuildMicrostructure(args) => commands::microstructure::build_microstructure(args),
        Commands::ImportSettlements(args) => commands::settlement::import_settlements(args),
        Commands::StoragePlan(args) => commands::storage_plan::storage_plan(args),
    }
}
