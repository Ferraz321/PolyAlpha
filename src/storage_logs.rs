use anyhow::Result;
use rusqlite::params;

use crate::storage::Storage;
use crate::storage_types::{ClobAssetFeature, RawClobEventRecord, RawEvmLogRecord};

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

    pub fn upsert_clob_feature(&self, feature: &ClobAssetFeature) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT INTO clob_asset_features (
                asset_id, market, best_bid, best_ask, spread, bid_depth, ask_depth, ofi,
                last_trade_price, last_trade_size, last_trade_side, last_event_type, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)
            ON CONFLICT(asset_id) DO UPDATE SET
                market = COALESCE(excluded.market, clob_asset_features.market),
                best_bid = COALESCE(excluded.best_bid, clob_asset_features.best_bid),
                best_ask = COALESCE(excluded.best_ask, clob_asset_features.best_ask),
                spread = COALESCE(excluded.spread, clob_asset_features.spread),
                bid_depth = COALESCE(excluded.bid_depth, clob_asset_features.bid_depth),
                ask_depth = COALESCE(excluded.ask_depth, clob_asset_features.ask_depth),
                ofi = COALESCE(excluded.ofi, clob_asset_features.ofi),
                last_trade_price = COALESCE(excluded.last_trade_price, clob_asset_features.last_trade_price),
                last_trade_size = COALESCE(excluded.last_trade_size, clob_asset_features.last_trade_size),
                last_trade_side = COALESCE(excluded.last_trade_side, clob_asset_features.last_trade_side),
                last_event_type = excluded.last_event_type,
                updated_at = excluded.updated_at
            "#,
            params![
                feature.asset_id,
                feature.market,
                feature.best_bid,
                feature.best_ask,
                feature.spread,
                feature.bid_depth,
                feature.ask_depth,
                feature.ofi,
                feature.last_trade_price,
                feature.last_trade_size,
                feature.last_trade_side,
                feature.last_event_type,
                feature.updated_at,
            ],
        )?;
        Ok(())
    }
}
