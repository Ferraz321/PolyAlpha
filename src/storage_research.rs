use anyhow::Result;
use chrono::Utc;
use rusqlite::{OptionalExtension, params};
use serde::{Deserialize, Serialize};

use crate::storage::Storage;

#[derive(Debug, Clone, Serialize)]
pub struct ResearchStats {
    pub market_tokens: usize,
    pub markets: usize,
    pub outcomes: usize,
    pub positions: usize,
    pub wallet_pnl: usize,
    pub wallet_clusters: usize,
    pub factor_values: usize,
    pub factor_candidates: usize,
    pub factor_validations: usize,
    pub strategies: usize,
    pub signals: usize,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FactorCandidateRecord {
    pub factor_id: String,
    pub name: String,
    pub lifecycle_state: String,
    pub priority: i64,
    pub required_data: String,
    pub owner_module: Option<String>,
    pub hypothesis: Option<String>,
    pub evidence_json: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FactorValidationRecord {
    pub validation_id: String,
    pub factor_id: String,
    pub method: String,
    pub verdict: String,
    pub report_json: String,
    pub in_sample_score: Option<String>,
    pub out_of_sample_score: Option<String>,
    pub negative_control_score: Option<String>,
    pub stability_score: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct StrategyRecord {
    pub strategy_id: String,
    pub name: String,
    pub lifecycle_state: String,
    pub config_json: String,
    pub source_factors_json: String,
    pub risk_json: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SignalRecord {
    pub signal_id: String,
    pub strategy_id: String,
    pub account: Option<String>,
    pub market_id: Option<String>,
    pub outcome_id: Option<String>,
    pub signal_type: String,
    pub score: String,
    pub payload_json: String,
    pub emitted_at: String,
    pub status: String,
}

impl Storage {
    pub fn research_stats(&self) -> Result<ResearchStats> {
        self.init()?;
        Ok(ResearchStats {
            market_tokens: count(self, "market_tokens")?,
            markets: count(self, "markets")?,
            outcomes: count(self, "outcomes")?,
            positions: count(self, "positions")?,
            wallet_pnl: count(self, "wallet_pnl")?,
            wallet_clusters: count(self, "wallet_clusters")?,
            factor_values: count(self, "factor_values")?,
            factor_candidates: count(self, "factor_candidates")?,
            factor_validations: count(self, "factor_validations")?,
            strategies: count(self, "strategies")?,
            signals: count(self, "signals")?,
        })
    }

    pub fn upsert_factor_candidate(&self, candidate: &FactorCandidateRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT INTO factor_candidates (
                factor_id, name, lifecycle_state, priority, required_data,
                owner_module, hypothesis, evidence_json, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            ON CONFLICT(factor_id) DO UPDATE SET
                name = excluded.name,
                lifecycle_state = excluded.lifecycle_state,
                priority = excluded.priority,
                required_data = excluded.required_data,
                owner_module = excluded.owner_module,
                hypothesis = excluded.hypothesis,
                evidence_json = excluded.evidence_json,
                updated_at = excluded.updated_at
            "#,
            params![
                candidate.factor_id,
                candidate.name,
                candidate.lifecycle_state,
                candidate.priority,
                candidate.required_data,
                candidate.owner_module,
                candidate.hypothesis,
                candidate.evidence_json,
                Utc::now().to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn factor_candidate(&self, factor_id: &str) -> Result<Option<FactorCandidateRecord>> {
        self.init()?;
        self.raw_connection()
            .query_row(
                r#"
                SELECT factor_id, name, lifecycle_state, priority, required_data,
                       owner_module, hypothesis, evidence_json
                FROM factor_candidates
                WHERE factor_id = ?1
                "#,
                params![factor_id],
                factor_candidate_from_row,
            )
            .optional()
            .map_err(Into::into)
    }

    pub fn insert_factor_validation(&self, validation: &FactorValidationRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT OR REPLACE INTO factor_validations (
                validation_id, factor_id, method, in_sample_score, out_of_sample_score,
                negative_control_score, stability_score, verdict, report_json
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            "#,
            params![
                validation.validation_id,
                validation.factor_id,
                validation.method,
                validation.in_sample_score,
                validation.out_of_sample_score,
                validation.negative_control_score,
                validation.stability_score,
                validation.verdict,
                validation.report_json,
            ],
        )?;
        Ok(())
    }

    pub fn upsert_strategy_record(&self, strategy: &StrategyRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT INTO strategies (
                strategy_id, name, lifecycle_state, config_json,
                source_factors_json, risk_json, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
            ON CONFLICT(strategy_id) DO UPDATE SET
                name = excluded.name,
                lifecycle_state = excluded.lifecycle_state,
                config_json = excluded.config_json,
                source_factors_json = excluded.source_factors_json,
                risk_json = excluded.risk_json,
                updated_at = excluded.updated_at
            "#,
            params![
                strategy.strategy_id,
                strategy.name,
                strategy.lifecycle_state,
                strategy.config_json,
                strategy.source_factors_json,
                strategy.risk_json,
                Utc::now().to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn insert_signal_record(&self, signal: &SignalRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT OR REPLACE INTO signals (
                signal_id, strategy_id, account, market_id, outcome_id,
                signal_type, score, payload_json, emitted_at, status
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
            "#,
            params![
                signal.signal_id,
                signal.strategy_id,
                signal.account,
                signal.market_id,
                signal.outcome_id,
                signal.signal_type,
                signal.score,
                signal.payload_json,
                signal.emitted_at,
                signal.status,
            ],
        )?;
        Ok(())
    }

    pub fn signal_count_for_strategy(&self, strategy_id: &str) -> Result<usize> {
        self.init()?;
        Ok(self.raw_connection().query_row(
            "SELECT COUNT(*) FROM signals WHERE strategy_id = ?1",
            params![strategy_id],
            |row| row.get::<_, i64>(0),
        )? as usize)
    }
}

fn count(storage: &Storage, table: &str) -> Result<usize> {
    let sql = format!("SELECT COUNT(*) FROM {table}");
    Ok(storage
        .raw_connection()
        .query_row(&sql, [], |row| row.get::<_, i64>(0))? as usize)
}

fn factor_candidate_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<FactorCandidateRecord> {
    Ok(FactorCandidateRecord {
        factor_id: row.get(0)?,
        name: row.get(1)?,
        lifecycle_state: row.get(2)?,
        priority: row.get(3)?,
        required_data: row.get(4)?,
        owner_module: row.get(5)?,
        hypothesis: row.get(6)?,
        evidence_json: row.get(7)?,
    })
}
