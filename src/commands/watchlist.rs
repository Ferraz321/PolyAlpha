use std::fs;

use anyhow::{Context, Result};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_watchlist::WatchlistEntry;

use crate::app::cli::ImportWatchlistArgs;

pub fn import_watchlist(args: ImportWatchlistArgs) -> Result<()> {
    let content = fs::read_to_string(&args.input)
        .with_context(|| format!("failed to read {}", args.input.display()))?;
    let entries = content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .filter_map(parse_line)
        .collect::<Vec<_>>();

    let mut storage = Storage::open(&args.db)?;
    let count = storage.upsert_watchlist(&entries, &args.source)?;
    println!(
        "watchlist: imported={}, source={}, db={}",
        count,
        args.source,
        args.db.display()
    );
    Ok(())
}

fn parse_line(line: &str) -> Option<WatchlistEntry> {
    let mut parts = line.splitn(2, ',').map(str::trim);
    let account = parts.next()?.to_ascii_lowercase();
    if !account.starts_with("0x") {
        return None;
    }
    let label = parts
        .next()
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned);
    Some(WatchlistEntry { account, label })
}
