use anyhow::{Context, Result};
use serde::Serialize;

use crate::storage::Storage;

#[derive(Debug, Serialize)]
pub struct ProfilerClobRow {
    pub asset_id: String,
    pub received_at: String,
    pub event_type: Option<String>,
    pub payload: String,
}

impl Storage {
    pub fn load_profiler_clob_rows(&self) -> Result<Vec<ProfilerClobRow>> {
        self.init()?;
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT asset_id, received_at, event_type, payload
            FROM raw_clob_events
            ORDER BY received_at ASC
            "#,
        )?;
        let rows = stmt.query_map([], |row| {
            Ok(ProfilerClobRow {
                asset_id: row.get::<_, Option<String>>(0)?.unwrap_or_default(),
                received_at: row.get(1)?,
                event_type: row.get(2)?,
                payload: row.get(3)?,
            })
        })?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .context("failed to load profiler clob rows")
    }
}
