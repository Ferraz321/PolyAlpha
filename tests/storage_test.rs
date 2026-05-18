use chrono::TimeZone;
use oktrader_alpha::microstructure::{JoinConfig, build_wallet_microstructure};
use oktrader_alpha::model::{FillEvent, LiquidityRole, TradeSide};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::{RawClobEventRecord, RawEvmLogRecord};
use oktrader_alpha::wallet_intelligence::build_wallet_intelligence;
use rust_decimal_macros::dec;

#[test]
fn stores_state_and_dedupes_raw_logs() {
    let mut storage = Storage::open(":memory:").expect("storage");
    storage.set_state("cursor", "42").expect("set state");
    assert_eq!(
        storage.get_state("cursor").expect("get state"),
        Some("42".to_string())
    );

    let log = RawEvmLogRecord {
        contract_address: "0xabc".to_string(),
        block_number: 1,
        transaction_hash: "0xtx".to_string(),
        log_index: 0,
        topic0: Some("0xtopic".to_string()),
        data: "0x".to_string(),
    };

    assert_eq!(storage.insert_raw_evm_logs(&[log]).expect("insert"), 1);
    assert_eq!(storage.stats().expect("stats").raw_evm_logs, 1);
}

#[test]
fn stores_and_dedupes_raw_clob_events() {
    let storage = Storage::open(":memory:").expect("open");
    storage.init().expect("init");

    let event = RawClobEventRecord {
        channel: "market".to_string(),
        event_type: Some("book".to_string()),
        asset_id: Some("123".to_string()),
        payload: r#"{"event_type":"book","asset_id":"123"}"#.to_string(),
        received_at: "2026-01-01T00:00:00Z".to_string(),
        stable_key: "clob-test-key".to_string(),
    };

    assert!(storage.insert_raw_clob_event(&event).expect("insert"));
    assert!(!storage.insert_raw_clob_event(&event).expect("dedupe"));
    assert_eq!(storage.stats().expect("stats").raw_clob_events, 1);
}

#[test]
fn stores_clob_asset_features() {
    let storage = Storage::open(":memory:").expect("open");
    storage.init().expect("init");
    let feature = oktrader_alpha::storage_types::ClobAssetFeature {
        asset_id: "123".to_string(),
        best_bid: Some("0.49".to_string()),
        best_ask: Some("0.51".to_string()),
        spread: Some("0.02".to_string()),
        last_event_type: "best_bid_ask".to_string(),
        updated_at: "2026-01-01T00:00:00Z".to_string(),
        ..Default::default()
    };

    storage.upsert_clob_feature(&feature).expect("feature");
    assert_eq!(storage.stats().expect("stats").clob_asset_features, 1);
}

#[test]
fn joins_wallet_fills_to_clob_microstructure() {
    let storage = Storage::open(":memory:").expect("open");
    storage.init().expect("init");
    let payload = r#"{
        "event_type":"price_change",
        "market":"m1",
        "price_changes":[
            {"asset_id":"m1","best_bid":"0.40","best_ask":"0.42","side":"BUY","size":"10"}
        ]
    }"#;
    let event = RawClobEventRecord {
        channel: "market".to_string(),
        event_type: Some("price_change".to_string()),
        asset_id: Some("m1".to_string()),
        payload: payload.to_string(),
        received_at: "2026-01-01T00:00:00+00:00".to_string(),
        stable_key: "clob-join-test".to_string(),
    };
    storage.insert_raw_clob_event(&event).expect("event");

    let fills = vec![custom_fill(
        "0xabc",
        "m1",
        TradeSide::Buy,
        dec!(0.41),
        dec!(100),
    )];
    let metrics = build_wallet_microstructure(
        &storage,
        &fills,
        JoinConfig {
            pre_secs: 10,
            post_secs: 10,
            event_limit: 5,
        },
    )
    .expect("microstructure");

    assert_eq!(metrics.len(), 1);
    assert_eq!(metrics[0].observed_fills, 1);
    assert_eq!(metrics[0].favorable_ofi_rate, "1");
}

#[test]
fn insert_fills_marks_wallet_dirty() {
    let mut storage = Storage::open(":memory:").expect("storage");
    storage
        .insert_fills(&[fill("0xabc")])
        .expect("insert fills");

    assert_eq!(storage.dirty_wallets(10).expect("dirty"), vec!["0xabc"]);
    storage
        .clear_dirty_wallets(&["0xabc".to_string()])
        .expect("clear");
    assert!(storage.dirty_wallets(10).expect("dirty").is_empty());
}

#[test]
fn fill_identity_keeps_same_second_partial_fills() {
    let mut storage = Storage::open(":memory:").expect("storage");
    let first = custom_fill("0xabc", "123", TradeSide::Buy, dec!(0.5), dec!(10));
    let mut second = custom_fill("0xabc", "123", TradeSide::Buy, dec!(0.51), dec!(15));
    second.order_hash = Some("0xorder-2".to_string());

    let summary = storage
        .insert_fills(&[first, second])
        .expect("insert fills");

    assert_eq!(summary.inserted_fills, 2);
    assert_eq!(storage.stats().expect("stats").fills, 2);
}

#[test]
fn stores_wallet_intelligence_snapshots() {
    let mut storage = Storage::open(":memory:").expect("storage");
    let fills = vec![
        custom_fill("0xabc", "m1", TradeSide::Buy, dec!(0.40), dec!(100)),
        custom_fill("0xabc", "m1", TradeSide::Sell, dec!(0.70), dec!(40)),
    ];
    let snapshot = build_wallet_intelligence(&fills).expect("snapshot");

    storage
        .replace_wallet_intelligence(&snapshot.positions, &snapshot.wallet_pnl)
        .expect("replace intelligence");

    let stats = storage.research_stats().expect("stats");
    assert_eq!(stats.positions, 1);
    assert_eq!(stats.wallet_pnl, 1);
}

fn fill(account: &str) -> FillEvent {
    custom_fill(account, "123", TradeSide::Buy, dec!(0.5), dec!(1))
}

fn custom_fill(
    account: &str,
    market_id: &str,
    side: TradeSide,
    price: rust_decimal::Decimal,
    shares: rust_decimal::Decimal,
) -> FillEvent {
    FillEvent {
        account: account.to_string(),
        market_id: market_id.to_string(),
        condition_id: None,
        event_slug: None,
        sector: None,
        side,
        role: LiquidityRole::Taker,
        price,
        shares,
        timestamp: chrono::Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap(),
        tx_hash: Some("0xtx".to_string()),
        order_hash: Some("0xorder".to_string()),
    }
}
