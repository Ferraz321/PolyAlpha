use std::collections::HashMap;

use anyhow::{Context, Result};
use oktrader_alpha::model::FillEvent;
use oktrader_alpha::storage::Storage;

use crate::app::cli::BackfillPolygonArgs;
use crate::chain::evm_rpc::{EvmLog, EvmRpc};
use crate::commands::backfill_decode::{
    ORDER_FILLED_SIG, ORDER_FILLED_V2_SIG, decode_order_filled, event_topic,
};

const NEG_RISK_EXCHANGE: &str = "0xe2222d279d744050d28e00520010520000310F59";

pub async fn backfill_polygon(args: BackfillPolygonArgs) -> Result<()> {
    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let rpc = EvmRpc::new(args.rpc_url.clone());
    let end_block = resolve_to_block(&rpc, &args.to_block).await?;
    let topics = vec![
        event_topic(ORDER_FILLED_SIG),
        event_topic(ORDER_FILLED_V2_SIG),
    ];
    let exchanges = exchange_addresses(&args);
    let mut block = args.from_block;
    let mut block_times = HashMap::new();

    while block <= end_block {
        let to_block = end_block.min(block + args.batch_blocks.saturating_sub(1));
        let all_logs = fetch_logs(&rpc, &exchanges, &topics, block, to_block).await?;
        let raw_logs = all_logs
            .iter()
            .filter_map(|log| log.raw_record().ok())
            .collect::<Vec<_>>();
        let raw_inserted = storage.insert_raw_evm_logs(&raw_logs)?;
        let log_count = all_logs.len();
        let fills = decode_logs(&rpc, all_logs, &mut block_times, &exchanges).await?;
        let summary = storage.insert_fills(&fills)?;
        storage.set_state("backfill_polygon.last_block", &to_block.to_string())?;
        println!(
            "backfill: blocks={}-{}, logs={}, raw_inserted={}, inserted_fills={}, new_wallets={}",
            block, to_block, log_count, raw_inserted, summary.inserted_fills, summary.new_wallets
        );

        if args.once {
            break;
        }
        block = to_block + 1;
    }

    Ok(())
}

async fn fetch_logs(
    rpc: &EvmRpc,
    exchanges: &[String],
    topics: &[String],
    from_block: u64,
    to_block: u64,
) -> Result<Vec<EvmLog>> {
    let mut all_logs = Vec::new();
    for exchange in exchanges {
        for topic in topics {
            let logs = rpc
                .logs(exchange, topic, from_block, to_block)
                .await
                .with_context(|| format!("failed logs {exchange} {from_block}-{to_block}"))?;
            all_logs.extend(logs);
        }
    }
    Ok(all_logs)
}

fn exchange_addresses(args: &BackfillPolygonArgs) -> Vec<String> {
    let mut exchanges = if args.exchanges.is_empty() {
        vec![args.ctf_exchange.clone()]
    } else {
        args.exchanges.clone()
    };
    if args.include_neg_risk {
        exchanges.push(NEG_RISK_EXCHANGE.to_string());
    }
    exchanges.sort();
    exchanges.dedup();
    exchanges
}

async fn resolve_to_block(rpc: &EvmRpc, to_block: &str) -> Result<u64> {
    if to_block == "latest" {
        rpc.block_number().await
    } else {
        Ok(to_block.parse()?)
    }
}

async fn decode_logs(
    rpc: &EvmRpc,
    logs: Vec<EvmLog>,
    block_times: &mut HashMap<u64, i64>,
    exchange_addresses: &[String],
) -> Result<Vec<FillEvent>> {
    let mut fills = Vec::new();
    for log in logs {
        let block_number = log.block_number_u64()?;
        let timestamp = match block_times.get(&block_number) {
            Some(timestamp) => *timestamp,
            None => {
                let timestamp = rpc.block_timestamp(block_number).await?;
                block_times.insert(block_number, timestamp);
                timestamp
            }
        };
        match decode_order_filled(log, timestamp, exchange_addresses) {
            Ok(decoded) => fills.extend(decoded),
            Err(error) => tracing::warn!(%error, "skipping undecodable OrderFilled log"),
        }
    }
    Ok(fills)
}
