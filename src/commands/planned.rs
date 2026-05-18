use std::collections::HashMap;
use std::time::Duration;

use anyhow::{Result, bail};
use oktrader_alpha::storage::Storage;

use crate::app::cli::WatchLiveArgs;
use crate::chain::evm_rpc::EvmRpc;
use crate::commands::backfill::{decode_logs, exchange_addresses, fetch_logs, order_filled_topics};

const NEXT_BLOCK_KEY: &str = "watch_live.next_block";
const LAST_BLOCK_KEY: &str = "watch_live.last_block";

pub async fn watch_live(args: WatchLiveArgs) -> Result<()> {
    if args.max_blocks_per_cycle == 0 {
        bail!("--max-blocks-per-cycle must be greater than zero");
    }

    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let rpc = EvmRpc::new(args.rpc_url.clone());
    let exchanges = exchange_addresses(&args.ctf_exchange, &args.exchanges, args.include_neg_risk);
    let topics = order_filled_topics();
    let mut block_times = HashMap::new();

    loop {
        let latest = rpc.block_number().await?;
        let from_block = next_from_block(&storage, latest, args.lookback_blocks)?;
        let to_block = latest.min(from_block + args.max_blocks_per_cycle - 1);

        if from_block <= to_block {
            let all_logs = fetch_logs(&rpc, &exchanges, &topics, from_block, to_block).await?;
            let raw_logs = all_logs
                .iter()
                .filter_map(|log| log.raw_record().ok())
                .collect::<Vec<_>>();
            let raw_inserted = storage.insert_raw_evm_logs(&raw_logs)?;
            let log_count = all_logs.len();
            let fills = decode_logs(&rpc, all_logs, &mut block_times, &exchanges).await?;
            let summary = storage.insert_fills(&fills)?;

            storage.set_state(LAST_BLOCK_KEY, &to_block.to_string())?;
            storage.set_state(NEXT_BLOCK_KEY, &(to_block + 1).to_string())?;
            println!(
                "watch-live: blocks={}-{}, logs={}, raw_inserted={}, inserted_fills={}, new_wallets={}",
                from_block,
                to_block,
                log_count,
                raw_inserted,
                summary.inserted_fills,
                summary.new_wallets
            );
        } else {
            println!("watch-live: caught up at block {}", latest);
        }

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

fn next_from_block(storage: &Storage, latest: u64, lookback_blocks: u64) -> Result<u64> {
    match storage.get_state(NEXT_BLOCK_KEY)? {
        Some(value) => Ok(value.parse()?),
        None => Ok(latest.saturating_sub(lookback_blocks)),
    }
}
