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
    }
}
