use anyhow::{Context, Result};
use chrono::{DateTime, Duration, Utc};
use rusqlite::params;

use crate::storage::Storage;
use crate::storage_types::{StoredClobEvent, WalletMicrostructureMetric};

impl Storage {
    pub fn clob_events_around_fill(
        &self,
        asset_id: &str,
        timestamp: DateTime<Utc>,
        pre_secs: i64,
        post_secs: i64,
        limit: usize,
    ) -> Result<Vec<StoredClobEvent>> {
        self.init()?;
        let from = (timestamp - Duration::seconds(pre_secs)).to_rfc3339();
        let to = (timestamp + Duration::seconds(post_secs)).to_rfc3339();
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT payload, received_at
            FROM raw_clob_events
            WHERE asset_id = ?1 AND received_at BETWEEN ?2 AND ?3
            ORDER BY ABS(strftime('%s', received_at) - strftime('%s', ?4)) ASC
            LIMIT ?5
            "#,
        )?;
        let rows = stmt.query_map(
            params![asset_id, from, to, timestamp.to_rfc3339(), limit],
            |row| {
                Ok(StoredClobEvent {
                    payload: row.get(0)?,
                    received_at: row.get(1)?,
                })
            },
        )?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load clob events around fill")
    }

    pub fn replace_wallet_microstructure(
        &mut self,
        metrics: &[WalletMicrostructureMetric],
    ) -> Result<()> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        tx.execute("DELETE FROM wallet_microstructure_metrics", [])?;
        for metric in metrics {
            tx.execute(
                r#"
                INSERT INTO wallet_microstructure_metrics (
                    account, observed_fills, avg_spread, avg_ofi, favorable_ofi_rate, updated_at
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                "#,
                params![
                    metric.account,
                    metric.observed_fills,
                    metric.avg_spread,
                    metric.avg_ofi,
                    metric.favorable_ofi_rate,
                    metric.updated_at,
                ],
            )?;
        }
        tx.commit()?;
        Ok(())
    }

    pub fn wallet_microstructure_map(
        &self,
    ) -> Result<std::collections::HashMap<String, WalletMicrostructureMetric>> {
        self.init()?;
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT account, observed_fills, avg_spread, avg_ofi, favorable_ofi_rate, updated_at
            FROM wallet_microstructure_metrics
            "#,
        )?;
        let rows = stmt.query_map([], |row| {
            let observed: i64 = row.get(1)?;
            Ok(WalletMicrostructureMetric {
                account: row.get(0)?,
                observed_fills: observed as usize,
                avg_spread: row.get(2)?,
                avg_ofi: row.get(3)?,
                favorable_ofi_rate: row.get(4)?,
                updated_at: row.get(5)?,
            })
        })?;

        let metrics = rows.collect::<rusqlite::Result<Vec<_>>>()?;
        Ok(metrics
            .into_iter()
            .map(|metric| (metric.account.clone(), metric))
            .collect())
    }
}
