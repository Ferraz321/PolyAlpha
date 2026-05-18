mod cli;
mod legacy_csv;
mod planned;
mod processes;
mod report;
mod taxonomy;

use anyhow::Result;
use clap::Parser;
use cli::{Cli, Commands};
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    match Cli::parse().command {
        Commands::InitDb(args) => processes::init_db(args.db),
        Commands::CollectorDataApi(args) => processes::collector_data_api(args).await,
        Commands::Analyzer(args) => processes::analyzer(args).await,
        Commands::Monitor(args) => processes::monitor(args).await,
        Commands::Export(args) => processes::export_matched(args),
        Commands::AnalyzeCsv(args) => legacy_csv::analyze_csv(args),
        Commands::ScanDataApi(args) => legacy_csv::scan_data_api(args).await,
        Commands::ListTaxonomy => {
            taxonomy::print_taxonomy();
            Ok(())
        }
        Commands::BackfillPolygon(args) => planned::backfill_polygon(args),
        Commands::WatchLive(args) => planned::watch_live(args),
    }
}
