use anyhow::{Result, bail};
use oktrader_alpha::microstructure::{JoinConfig, build_wallet_microstructure};
use oktrader_alpha::storage::Storage;

use crate::app::cli::BuildMicrostructureArgs;

pub fn build_microstructure(args: BuildMicrostructureArgs) -> Result<()> {
    if args.pre_secs < 0 || args.post_secs < 0 {
        bail!("pre/post windows must be non-negative");
    }
    if args.event_limit == 0 {
        bail!("--event-limit must be greater than zero");
    }

    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let fills = storage.load_fills()?;
    let metrics = build_wallet_microstructure(
        &storage,
        &fills,
        JoinConfig {
            pre_secs: args.pre_secs,
            post_secs: args.post_secs,
            event_limit: args.event_limit,
        },
    )?;
    storage.replace_wallet_microstructure(&metrics)?;
    println!(
        "microstructure: fills={}, wallet_metrics={}",
        fills.len(),
        metrics.len()
    );
    Ok(())
}
