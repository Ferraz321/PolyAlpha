use chrono::TimeZone;
use oktrader_alpha::model::{FillEvent, LiquidityRole, TradeSide};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::RawEvmLogRecord;
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

fn fill(account: &str) -> FillEvent {
    FillEvent {
        account: account.to_string(),
        market_id: "123".to_string(),
        condition_id: None,
        event_slug: None,
        sector: None,
        side: TradeSide::Buy,
        role: LiquidityRole::Taker,
        price: dec!(0.5),
        shares: dec!(1),
        timestamp: chrono::Utc.with_ymd_and_hms(2026, 1, 1, 0, 0, 0).unwrap(),
        tx_hash: Some("0xtx".to_string()),
        order_hash: Some("0xorder".to_string()),
    }
}
