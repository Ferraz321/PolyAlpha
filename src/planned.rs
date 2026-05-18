use anyhow::Result;
use oktrader_alpha::storage::Storage;

use crate::cli::{BackfillPolygonArgs, DbArgs};

pub fn backfill_polygon(args: BackfillPolygonArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    storage.init()?;
    println!(
        "backfill-polygon planned: db={}, rpc_url={}, from_block={}, to_block={}. Next: eth_getLogs batching + CTFExchange OrderFilled decoding.",
        args.db.display(),
        args.rpc_url,
        args.from_block,
        args.to_block
    );
    Ok(())
}

pub fn watch_live(args: DbArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    storage.init()?;
    println!(
        "watch-live planned: db={}. Next: Polygon new-block subscription + Polymarket CLOB websocket ingestion.",
        args.db.display()
    );
    Ok(())
}
