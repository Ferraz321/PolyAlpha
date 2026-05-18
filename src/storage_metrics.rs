use anyhow::{Context, Result};
use chrono::Utc;
use rusqlite::params;

use crate::storage::Storage;
use crate::storage_types::MetricParts;

impl Storage {
    pub fn replace_account_metrics<T>(
        &mut self,
        reports: &[T],
        to_parts: impl Fn(&T) -> Result<MetricParts>,
    ) -> Result<()> {
        self.init()?;
        let tx = self.raw_connection_mut().transaction()?;
        let updated_at = Utc::now().to_rfc3339();

        for report in reports {
            let parts = to_parts(report)?;
            tx.execute(
                r#"
                INSERT INTO account_metrics (
                    account, metrics_json, classification_json, passed_funnel,
                    failed_reasons_json, updated_at
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6)
                ON CONFLICT(account) DO UPDATE SET
                    metrics_json = excluded.metrics_json,
                    classification_json = excluded.classification_json,
                    passed_funnel = excluded.passed_funnel,
                    failed_reasons_json = excluded.failed_reasons_json,
                    updated_at = excluded.updated_at
                "#,
                params![
                    parts.account,
                    parts.metrics_json,
                    parts.classification_json,
                    i64::from(parts.passed_funnel),
                    parts.failed_reasons_json,
                    updated_at,
                ],
            )?;
        }

        tx.commit()?;
        Ok(())
    }

    pub fn load_account_report_json(&self) -> Result<Vec<String>> {
        self.init()?;
        let mut stmt = self.raw_connection().prepare(
            "SELECT metrics_json, classification_json, passed_funnel, failed_reasons_json FROM account_metrics",
        )?;
        let rows = stmt.query_map([], |row| {
            let metrics: String = row.get(0)?;
            let classification: String = row.get(1)?;
            let passed: i64 = row.get(2)?;
            let reasons: String = row.get(3)?;
            Ok((metrics, classification, passed, reasons))
        })?;
        rows.map(|row| {
            let (metrics, classification, passed, reasons) = row?;
            Ok(format!(
                "{{{},\"passed_funnel\":{},\"failed_reasons\":{}, {}}}",
                trim_braces(&metrics),
                passed == 1,
                reasons,
                trim_braces(&classification)
            ))
        })
        .collect::<rusqlite::Result<Vec<_>>>()
        .context("failed to load account report json")
    }
}

fn trim_braces(json: &str) -> &str {
    json.trim_start_matches('{').trim_end_matches('}')
}
