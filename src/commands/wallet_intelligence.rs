use anyhow::Result;
use oktrader_alpha::storage::Storage;
use oktrader_alpha::wallet_intelligence::build_wallet_intelligence_with_context;

use crate::app::cli::DbArgs;

pub fn build_wallet_intelligence_command(args: DbArgs) -> Result<()> {
    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let fills = storage.load_fills()?;
    let context = storage.wallet_intelligence_context()?;
    let snapshot = build_wallet_intelligence_with_context(&fills, &context)?;
    storage.replace_wallet_intelligence(&snapshot.positions, &snapshot.wallet_pnl)?;
    println!(
        "wallet-intelligence: fills={}, positions={}, wallet_pnl={}",
        fills.len(),
        snapshot.positions.len(),
        snapshot.wallet_pnl.len()
    );
    Ok(())
}
