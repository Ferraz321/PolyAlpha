use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::RawEvmLogRecord;

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
