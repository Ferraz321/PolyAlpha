use anyhow::Result;
use rusqlite::params;

use crate::storage::Storage;
use crate::strategy_config::FeatureSnapshot;

impl Storage {
    pub fn latest_feature_snapshot(&self, asset_id: &str) -> Result<Option<FeatureSnapshot>> {
        self.init()?;
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT ofi, spread, bid_depth, ask_depth
            FROM clob_asset_features
            WHERE asset_id = ?1
            "#,
        )?;
        let mut rows = stmt.query(params![asset_id])?;
        let Some(row) = rows.next()? else {
            return Ok(None);
        };
        let bid_depth = parse_optional(row.get::<_, Option<String>>(2)?);
        let ask_depth = parse_optional(row.get::<_, Option<String>>(3)?);
        Ok(Some(FeatureSnapshot {
            ofi: parse_optional(row.get::<_, Option<String>>(0)?),
            spread: parse_optional(row.get::<_, Option<String>>(1)?),
            price_momentum: None,
            depth_imbalance: depth_imbalance(bid_depth, ask_depth),
        }))
    }
}

fn parse_optional(value: Option<String>) -> Option<f64> {
    value.and_then(|raw| raw.parse::<f64>().ok())
}

fn depth_imbalance(bid_depth: Option<f64>, ask_depth: Option<f64>) -> Option<f64> {
    let bid_depth = bid_depth?;
    let ask_depth = ask_depth?;
    let total = bid_depth + ask_depth;
    if total == 0.0 {
        Some(0.0)
    } else {
        Some((bid_depth - ask_depth) / total)
    }
}
