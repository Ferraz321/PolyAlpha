use anyhow::Result;
use oktrader_alpha::storage::Storage;

use crate::cli::DbArgs;

pub fn watch_live(args: DbArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    storage.init()?;
    println!(
        "watch-live planned: db={}. Next: Polygon new-block subscription + Polymarket CLOB websocket ingestion.",
        args.db.display()
    );
    Ok(())
}
