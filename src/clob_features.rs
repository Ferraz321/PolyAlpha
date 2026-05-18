use anyhow::Result;
use rust_decimal::Decimal;
use serde_json::Value;

use crate::storage_types::ClobAssetFeature;

pub fn features_from_payload(payload: &str, received_at: &str) -> Result<Vec<ClobAssetFeature>> {
    let value: Value = serde_json::from_str(payload)?;
    match value {
        Value::Array(items) => items
            .iter()
            .map(|item| features_from_value(item, received_at))
            .collect::<Result<Vec<_>>>()
            .map(|nested| nested.into_iter().flatten().collect()),
        item => features_from_value(&item, received_at),
    }
}

fn features_from_value(value: &Value, received_at: &str) -> Result<Vec<ClobAssetFeature>> {
    match str_field(value, "event_type").as_deref() {
        Some("book") => Ok(str_field(value, "asset_id")
            .map(|asset_id| vec![book_feature(value, asset_id, received_at)])
            .unwrap_or_default()),
        Some("best_bid_ask") => Ok(str_field(value, "asset_id")
            .map(|asset_id| vec![bbo_feature(value, asset_id, received_at)])
            .unwrap_or_default()),
        Some("last_trade_price") => Ok(str_field(value, "asset_id")
            .map(|asset_id| vec![trade_feature(value, asset_id, received_at)])
            .unwrap_or_default()),
        Some("price_change") => price_change_features(value, received_at),
        _ => Ok(Vec::new()),
    }
}

fn book_feature(value: &Value, asset_id: String, received_at: &str) -> ClobAssetFeature {
    let bids = value.get("bids").and_then(Value::as_array);
    let asks = value.get("asks").and_then(Value::as_array);
    let bid_depth = depth(bids);
    let ask_depth = depth(asks);
    ClobAssetFeature {
        asset_id,
        market: str_field(value, "market"),
        best_bid: best_price(bids, true),
        best_ask: best_price(asks, false),
        spread: None,
        bid_depth: bid_depth.map(|v| v.to_string()),
        ask_depth: ask_depth.map(|v| v.to_string()),
        ofi: ofi(bid_depth, ask_depth),
        last_event_type: "book".to_string(),
        updated_at: received_at.to_string(),
        ..Default::default()
    }
}

fn bbo_feature(value: &Value, asset_id: String, received_at: &str) -> ClobAssetFeature {
    ClobAssetFeature {
        asset_id,
        market: str_field(value, "market"),
        best_bid: str_field(value, "best_bid"),
        best_ask: str_field(value, "best_ask"),
        spread: str_field(value, "spread").or_else(|| spread(value)),
        last_event_type: "best_bid_ask".to_string(),
        updated_at: received_at.to_string(),
        ..Default::default()
    }
}

fn trade_feature(value: &Value, asset_id: String, received_at: &str) -> ClobAssetFeature {
    ClobAssetFeature {
        asset_id,
        market: str_field(value, "market"),
        last_trade_price: str_field(value, "price"),
        last_trade_size: str_field(value, "size"),
        last_trade_side: str_field(value, "side"),
        last_event_type: "last_trade_price".to_string(),
        updated_at: received_at.to_string(),
        ..Default::default()
    }
}

fn price_change_features(value: &Value, received_at: &str) -> Result<Vec<ClobAssetFeature>> {
    let Some(changes) = value.get("price_changes").and_then(Value::as_array) else {
        return Ok(Vec::new());
    };
    Ok(changes
        .iter()
        .filter_map(|change| {
            let asset_id = str_field(change, "asset_id")?;
            Some(ClobAssetFeature {
                asset_id,
                market: str_field(value, "market"),
                best_bid: str_field(change, "best_bid"),
                best_ask: str_field(change, "best_ask"),
                spread: spread(change),
                ofi: signed_size(change),
                last_event_type: "price_change".to_string(),
                updated_at: received_at.to_string(),
                ..Default::default()
            })
        })
        .collect())
}

fn str_field(value: &Value, key: &str) -> Option<String> {
    value
        .get(key)
        .and_then(Value::as_str)
        .map(ToOwned::to_owned)
}

fn best_price(levels: Option<&Vec<Value>>, is_bid: bool) -> Option<String> {
    let mut prices = levels?
        .iter()
        .filter_map(|level| decimal_field(level, "price"))
        .collect::<Vec<_>>();
    prices.sort();
    let price = if is_bid {
        prices.pop()?
    } else {
        prices.first().copied()?
    };
    Some(price.to_string())
}

fn depth(levels: Option<&Vec<Value>>) -> Option<Decimal> {
    Some(
        levels?
            .iter()
            .filter_map(|level| decimal_field(level, "size"))
            .sum(),
    )
}

fn ofi(bid_depth: Option<Decimal>, ask_depth: Option<Decimal>) -> Option<String> {
    let bid = bid_depth?;
    let ask = ask_depth?;
    let total = bid + ask;
    (total != Decimal::ZERO).then(|| ((bid - ask) / total).to_string())
}

fn spread(value: &Value) -> Option<String> {
    let bid = decimal_field(value, "best_bid")?;
    let ask = decimal_field(value, "best_ask")?;
    Some((ask - bid).to_string())
}

fn signed_size(value: &Value) -> Option<String> {
    let size = decimal_field(value, "size")?;
    match str_field(value, "side").as_deref() {
        Some("BUY") => Some(size.to_string()),
        Some("SELL") => Some((-size).to_string()),
        _ => None,
    }
}

fn decimal_field(value: &Value, key: &str) -> Option<Decimal> {
    value.get(key)?.as_str()?.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_book_depth_and_ofi() {
        let payload = r#"{
            "event_type":"book",
            "asset_id":"a1",
            "market":"m1",
            "bids":[{"price":"0.49","size":"20"},{"price":"0.50","size":"30"}],
            "asks":[{"price":"0.52","size":"10"},{"price":"0.53","size":"15"}]
        }"#;

        let features = features_from_payload(payload, "2026-01-01T00:00:00Z").unwrap();
        assert_eq!(features[0].best_bid.as_deref(), Some("0.50"));
        assert_eq!(features[0].best_ask.as_deref(), Some("0.52"));
        assert_eq!(features[0].bid_depth.as_deref(), Some("50"));
        assert_eq!(features[0].ask_depth.as_deref(), Some("25"));
    }

    #[test]
    fn extracts_price_change_bbo_and_signed_flow() {
        let payload = r#"{
            "event_type":"price_change",
            "market":"m1",
            "price_changes":[
                {"asset_id":"a1","best_bid":"0.50","best_ask":"0.53","side":"SELL","size":"12"}
            ]
        }"#;

        let features = features_from_payload(payload, "2026-01-01T00:00:00Z").unwrap();
        assert_eq!(features[0].spread.as_deref(), Some("0.03"));
        assert_eq!(features[0].ofi.as_deref(), Some("-12"));
    }
}
