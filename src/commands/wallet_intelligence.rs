use anyhow::Result;
use oktrader_alpha::storage::Storage;
use oktrader_alpha::wallet_intelligence::build_wallet_intelligence;

use crate::app::cli::DbArgs;

pub fn build_wallet_intelligence_command(args: DbArgs) -> Result<()> {
    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let fills = storage.load_fills()?;
    let snapshot = build_wallet_intelligence(&fills)?;
    storage.replace_wallet_intelligence(&snapshot.positions, &snapshot.wallet_pnl)?;
    println!(
        "wallet-intelligence: fills={}, positions={}, wallet_pnl={}",
        fills.len(),
        snapshot.positions.len(),
        snapshot.wallet_pnl.len()
    );
    Ok(())
}
