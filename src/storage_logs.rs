use anyhow::Result;
use rusqlite::params;

use crate::storage::Storage;
use crate::storage_types::{RawClobEventRecord, RawEvmLogRecord};

impl Storage {
    pub fn insert_raw_evm_logs(&mut self, logs: &[RawEvmLogRecord]) -> Result<usize> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        let mut inserted = 0usize;

        for log in logs {
            inserted += tx.execute(
                r#"
                INSERT OR IGNORE INTO raw_evm_logs (
                    contract_address, block_number, transaction_hash, log_index, topic0, data
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                "#,
                params![
                    log.contract_address,
                    log.block_number,
                    log.transaction_hash,
                    log.log_index,
                    log.topic0,
                    log.data,
                ],
            )?;
        }

        tx.commit()?;
        Ok(inserted)
    }

    pub fn insert_raw_clob_event(&self, event: &RawClobEventRecord) -> Result<bool> {
        self.init()?;
        let inserted = self.raw_connection().execute(
            r#"
            INSERT OR IGNORE INTO raw_clob_events (
                channel, event_type, asset_id, payload, received_at, stable_key
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6)
            "#,
            params![
                event.channel,
                event.event_type,
                event.asset_id,
                event.payload,
                event.received_at,
                event.stable_key,
            ],
        )?;
        Ok(inserted == 1)
    }
}
