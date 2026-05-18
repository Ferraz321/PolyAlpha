use std::collections::HashMap;

use anyhow::{Context, Result, bail};
use chrono::{TimeZone, Utc};
use oktrader_alpha::model::{FillEvent, LiquidityRole, TradeSide};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::scale_6;
use rust_decimal::Decimal;
use tiny_keccak::{Hasher, Keccak};

use crate::cli::BackfillPolygonArgs;
use crate::evm_rpc::{EvmLog, EvmRpc, hex_u64};

const ORDER_FILLED_SIG: &str =
    "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)";
const NEG_RISK_EXCHANGE: &str = "0xe2222d279d744050d28e00520010520000310F59";

pub async fn backfill_polygon(args: BackfillPolygonArgs) -> Result<()> {
    let mut storage = Storage::open(&args.db)?;
    storage.init()?;
    let rpc = EvmRpc::new(args.rpc_url.clone());
    let end_block = resolve_to_block(&rpc, &args.to_block).await?;
    let topic0 = event_topic(ORDER_FILLED_SIG);
    let exchanges = exchange_addresses(&args);
    let mut block = args.from_block;
    let mut block_times = HashMap::new();

    while block <= end_block {
        let to_block = end_block.min(block + args.batch_blocks.saturating_sub(1));
        let mut all_logs = Vec::new();
        for exchange in &exchanges {
            let logs = rpc
                .logs(exchange, &topic0, block, to_block)
                .await
                .with_context(|| format!("failed logs {exchange} {block}-{to_block}"))?;
            all_logs.extend(logs);
        }
        let raw_logs = all_logs
            .iter()
            .filter_map(|log| log.raw_record().ok())
            .collect::<Vec<_>>();
        let raw_inserted = storage.insert_raw_evm_logs(&raw_logs)?;
        let log_count = all_logs.len();
        let fills = decode_logs(&rpc, all_logs, &mut block_times).await?;
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
) -> Result<Vec<FillEvent>> {
    let mut fills = Vec::new();
    for log in logs {
        let block_number = hex_u64(&log.block_number)?;
        let timestamp = match block_times.get(&block_number) {
            Some(timestamp) => *timestamp,
            None => {
                let timestamp = rpc.block_timestamp(block_number).await?;
                block_times.insert(block_number, timestamp);
                timestamp
            }
        };
        match decode_order_filled(log, timestamp) {
            Ok(fill) => fills.push(fill),
            Err(error) => tracing::warn!(%error, "skipping undecodable OrderFilled log"),
        }
    }
    Ok(fills)
}

fn decode_order_filled(log: EvmLog, timestamp: i64) -> Result<FillEvent> {
    if log.topics.len() < 4 {
        bail!("OrderFilled requires indexed orderHash, maker, taker");
    }
    let order_hash = log.topics[1].clone();
    let maker = topic_address(&log.topics[2])?;
    let words = data_words(&log.data)?;
    if words.len() < 5 {
        bail!("OrderFilled data must contain five uint256 words");
    }

    let maker_asset_id = word_decimal(&words[0])?;
    let taker_asset_id = word_decimal(&words[1])?;
    let maker_amount = scale_6(word_decimal(&words[2])?);
    let taker_amount = scale_6(word_decimal(&words[3])?);
    let (side, market_id, shares, price) =
        maker_side(maker_asset_id, taker_asset_id, maker_amount, taker_amount)?;

    Ok(FillEvent {
        account: maker,
        market_id,
        condition_id: None,
        event_slug: None,
        sector: None,
        side,
        role: LiquidityRole::Maker,
        price,
        shares,
        timestamp: Utc
            .timestamp_opt(timestamp, 0)
            .single()
            .context("bad block timestamp")?,
        tx_hash: Some(log.transaction_hash),
        order_hash: Some(order_hash),
    })
}

fn maker_side(
    maker_asset_id: Decimal,
    taker_asset_id: Decimal,
    maker_amount: Decimal,
    taker_amount: Decimal,
) -> Result<(TradeSide, String, Decimal, Decimal)> {
    if maker_asset_id == Decimal::ZERO && taker_amount > Decimal::ZERO {
        Ok((
            TradeSide::Buy,
            taker_asset_id.to_string(),
            taker_amount,
            maker_amount / taker_amount,
        ))
    } else if taker_asset_id == Decimal::ZERO && maker_amount > Decimal::ZERO {
        Ok((
            TradeSide::Sell,
            maker_asset_id.to_string(),
            maker_amount,
            taker_amount / maker_amount,
        ))
    } else {
        bail!("unsupported non-collateral maker/taker asset pair")
    }
}

fn event_topic(signature: &str) -> String {
    let mut hasher = Keccak::v256();
    let mut out = [0u8; 32];
    hasher.update(signature.as_bytes());
    hasher.finalize(&mut out);
    format!("0x{}", hex_encode(&out))
}

fn topic_address(topic: &str) -> Result<String> {
    let clean = topic.trim_start_matches("0x");
    if clean.len() != 64 {
        bail!("invalid address topic");
    }
    Ok(format!("0x{}", &clean[24..64]).to_ascii_lowercase())
}

fn data_words(data: &str) -> Result<Vec<String>> {
    let clean = data.trim_start_matches("0x");
    if !clean.len().is_multiple_of(64) {
        bail!("event data not word-aligned");
    }
    Ok(clean
        .as_bytes()
        .chunks(64)
        .map(|chunk| String::from_utf8_lossy(chunk).to_string())
        .collect())
}

fn word_decimal(word: &str) -> Result<Decimal> {
    let value = u128::from_str_radix(word, 16)?;
    Ok(Decimal::from(value))
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|byte| format!("{byte:02x}")).collect()
}
