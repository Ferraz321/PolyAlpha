use anyhow::{Context, Result, bail};
use chrono::{TimeZone, Utc};
use oktrader_alpha::model::{FillEvent, LiquidityRole, TradeSide};
use oktrader_alpha::storage_types::scale_6;
use rust_decimal::Decimal;
use tiny_keccak::{Hasher, Keccak};

use crate::chain::evm_rpc::EvmLog;

pub const ORDER_FILLED_SIG: &str =
    "OrderFilled(bytes32,address,address,uint256,uint256,uint256,uint256,uint256)";
pub const ORDER_FILLED_V2_SIG: &str =
    "OrderFilled(bytes32,address,address,uint8,uint256,uint256,uint256,uint256,bytes32,bytes32)";

pub fn decode_order_filled(
    log: EvmLog,
    timestamp: i64,
    exchange_addresses: &[String],
) -> Result<Vec<FillEvent>> {
    if log.topics.len() < 4 {
        bail!("OrderFilled requires indexed orderHash, maker, taker");
    }
    let order_hash = log.topics[1].clone();
    let maker = topic_address(&log.topics[2])?;
    let taker = topic_address(&log.topics[3])?;
    let words = data_words(&log.data)?;
    let (side, market_id, shares, price) = if words.len() >= 7 {
        decode_v2_words(&words)?
    } else {
        decode_v1_words(&words)?
    };
    let timestamp = Utc
        .timestamp_opt(timestamp, 0)
        .single()
        .context("bad block timestamp")?;
    let mut fills = vec![fill(
        maker,
        market_id.clone(),
        side,
        LiquidityRole::Maker,
        price,
        shares,
        timestamp,
        log.transaction_hash.clone(),
        order_hash.clone(),
    )];

    if should_reconstruct_taker(&taker, exchange_addresses) {
        fills.push(fill(
            taker,
            market_id,
            opposite_side(side),
            LiquidityRole::Taker,
            price,
            shares,
            timestamp,
            log.transaction_hash,
            order_hash,
        ));
    }

    Ok(fills)
}

pub fn event_topic(signature: &str) -> String {
    let mut hasher = Keccak::v256();
    let mut out = [0u8; 32];
    hasher.update(signature.as_bytes());
    hasher.finalize(&mut out);
    format!("0x{}", hex_encode(&out))
}

fn fill(
    account: String,
    market_id: String,
    side: TradeSide,
    role: LiquidityRole,
    price: Decimal,
    shares: Decimal,
    timestamp: chrono::DateTime<Utc>,
    tx_hash: String,
    order_hash: String,
) -> FillEvent {
    FillEvent {
        account,
        market_id,
        condition_id: None,
        event_slug: None,
        sector: None,
        side,
        role,
        price,
        shares,
        timestamp,
        tx_hash: Some(tx_hash),
        order_hash: Some(order_hash),
    }
}

fn decode_v1_words(words: &[String]) -> Result<(TradeSide, String, Decimal, Decimal)> {
    if words.len() < 5 {
        bail!("V1 OrderFilled data must contain five uint256 words");
    }
    let maker_asset_id = word_decimal(&words[0])?;
    let taker_asset_id = word_decimal(&words[1])?;
    let maker_amount = scale_6(word_decimal(&words[2])?);
    let taker_amount = scale_6(word_decimal(&words[3])?);
    maker_side(maker_asset_id, taker_asset_id, maker_amount, taker_amount)
}

fn decode_v2_words(words: &[String]) -> Result<(TradeSide, String, Decimal, Decimal)> {
    let side = match word_decimal(&words[0])? {
        value if value == Decimal::ZERO => TradeSide::Buy,
        value if value == Decimal::ONE => TradeSide::Sell,
        value => bail!("unknown V2 side value {value}"),
    };
    let token_id = word_decimal(&words[1])?.to_string();
    let maker_amount = scale_6(word_decimal(&words[2])?);
    let taker_amount = scale_6(word_decimal(&words[3])?);
    let (shares, price) = match side {
        TradeSide::Buy => (taker_amount, maker_amount / taker_amount),
        TradeSide::Sell => (maker_amount, taker_amount / maker_amount),
    };
    Ok((side, token_id, shares, price))
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

fn should_reconstruct_taker(taker: &str, exchange_addresses: &[String]) -> bool {
    !exchange_addresses
        .iter()
        .any(|exchange| exchange.eq_ignore_ascii_case(taker))
}

fn opposite_side(side: TradeSide) -> TradeSide {
    match side {
        TradeSide::Buy => TradeSide::Sell,
        TradeSide::Sell => TradeSide::Buy,
    }
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn decodes_v2_buy_words() {
        let words = vec![
            word(0),
            word(123),
            word(500_000),
            word(1_000_000),
            word(0),
            word(0),
            word(0),
        ];

        let (side, market_id, shares, price) = decode_v2_words(&words).expect("decode");

        assert_eq!(side, TradeSide::Buy);
        assert_eq!(market_id, "123");
        assert_eq!(shares, Decimal::ONE);
        assert_eq!(price, Decimal::new(5, 1));
    }

    #[test]
    fn decodes_v2_fixture_and_reconstructs_taker() {
        let mut log: EvmLog =
            serde_json::from_str(include_str!("../../tests/fixtures/order_filled_v2.json"))
                .expect("fixture");
        log.topics[0] = event_topic(ORDER_FILLED_V2_SIG);
        log.data = format!(
            "0x{}",
            [0, 123, 500_000, 1_000_000, 0, 0, 0]
                .into_iter()
                .map(word)
                .collect::<String>()
        );

        let fills = decode_order_filled(log, 1_700_000_000, &[]).expect("decode");

        assert_eq!(fills.len(), 2);
        assert_eq!(
            fills[0].account,
            "0x1111111111111111111111111111111111111111"
        );
        assert_eq!(fills[0].side, TradeSide::Buy);
        assert_eq!(
            fills[1].account,
            "0x2222222222222222222222222222222222222222"
        );
        assert_eq!(fills[1].side, TradeSide::Sell);
    }

    fn word(value: u128) -> String {
        format!("{value:064x}")
    }
}
