use anyhow::Result;
use chrono::{DateTime, Duration, Utc};
use rusqlite::{OptionalExtension, params};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};

use crate::storage::Storage;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletTradeEventRecord {
    pub event_id: String,
    pub fill_id: Option<i64>,
    pub account: String,
    pub market_id: String,
    pub outcome_id: Option<String>,
    pub side: String,
    pub price: Decimal,
    pub shares: Decimal,
    pub source_timestamp: String,
    pub observed_at: String,
    pub received_at: String,
    pub latency_ms: i64,
    pub source: String,
    pub payload_json: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FollowSignalRecord {
    pub signal_id: String,
    pub wallet_event_id: String,
    pub account: String,
    pub market_id: String,
    pub outcome_id: Option<String>,
    pub side: String,
    pub target_price: Decimal,
    pub copied_shares: Decimal,
    pub max_notional: Decimal,
    pub score: Decimal,
    pub verdict: String,
    pub reasons_json: String,
    pub emitted_at: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperFollowFillRecord {
    pub paper_fill_id: String,
    pub signal_id: String,
    pub wallet_event_id: String,
    pub entry_price: Decimal,
    pub shares: Decimal,
    pub notional: Decimal,
    pub slippage_bps: Decimal,
    pub depth_snapshot_json: String,
    pub depth_status: String,
    pub entry_at: String,
    pub exit_price: Option<Decimal>,
    pub exit_at: Option<String>,
    pub pnl: Option<Decimal>,
    pub pnl_bps: Option<Decimal>,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalletFollowScoreRecord {
    pub account: String,
    pub worth_following: String,
    pub latency_verdict: String,
    pub depth_verdict: String,
    pub edge_verdict: String,
    pub overall_verdict: String,
    pub score: Decimal,
    pub metrics_json: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FollowDepthSnapshot {
    pub asset_id: String,
    pub best_bid: Option<Decimal>,
    pub best_ask: Option<Decimal>,
    pub spread: Option<Decimal>,
    pub bid_depth: Option<Decimal>,
    pub ask_depth: Option<Decimal>,
    pub ofi: Option<Decimal>,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpenPaperFollowFill {
    pub paper_fill_id: String,
    pub market_id: String,
    pub side: String,
    pub entry_price: Decimal,
    pub shares: Decimal,
    pub entry_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketPricePoint {
    pub price: Decimal,
    pub timestamp: DateTime<Utc>,
}

impl Storage {
    pub fn upsert_wallet_trade_event(&self, event: &WalletTradeEventRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT INTO wallet_trade_events (
                event_id, fill_id, account, market_id, outcome_id, side, price, shares,
                source_timestamp, observed_at, received_at, latency_ms, source, payload_json
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)
            ON CONFLICT(event_id) DO UPDATE SET
                observed_at = excluded.observed_at,
                received_at = excluded.received_at,
                latency_ms = excluded.latency_ms,
                payload_json = excluded.payload_json
            "#,
            params![
                event.event_id,
                event.fill_id,
                event.account,
                event.market_id,
                event.outcome_id,
                event.side,
                event.price.to_string(),
                event.shares.to_string(),
                event.source_timestamp,
                event.observed_at,
                event.received_at,
                event.latency_ms,
                event.source,
                event.payload_json,
            ],
        )?;
        Ok(())
    }

    pub fn insert_follow_signal(&self, signal: &FollowSignalRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT OR REPLACE INTO follow_signals (
                signal_id, wallet_event_id, account, market_id, outcome_id, side,
                target_price, copied_shares, max_notional, score, verdict,
                reasons_json, emitted_at, status
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)
            "#,
            params![
                signal.signal_id,
                signal.wallet_event_id,
                signal.account,
                signal.market_id,
                signal.outcome_id,
                signal.side,
                signal.target_price.to_string(),
                signal.copied_shares.to_string(),
                signal.max_notional.to_string(),
                signal.score.to_string(),
                signal.verdict,
                signal.reasons_json,
                signal.emitted_at,
                signal.status,
            ],
        )?;
        Ok(())
    }

    pub fn insert_paper_follow_fill(&self, fill: &PaperFollowFillRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT OR REPLACE INTO paper_follow_fills (
                paper_fill_id, signal_id, wallet_event_id, entry_price, shares, notional,
                slippage_bps, depth_snapshot_json, depth_status, entry_at, exit_price,
                exit_at, pnl, pnl_bps, status
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15)
            "#,
            params![
                fill.paper_fill_id,
                fill.signal_id,
                fill.wallet_event_id,
                fill.entry_price.to_string(),
                fill.shares.to_string(),
                fill.notional.to_string(),
                fill.slippage_bps.to_string(),
                fill.depth_snapshot_json,
                fill.depth_status,
                fill.entry_at,
                fill.exit_price.map(|value| value.to_string()),
                fill.exit_at,
                fill.pnl.map(|value| value.to_string()),
                fill.pnl_bps.map(|value| value.to_string()),
                fill.status,
            ],
        )?;
        Ok(())
    }

    pub fn upsert_wallet_follow_score(&self, score: &WalletFollowScoreRecord) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            INSERT INTO wallet_follow_scores (
                account, worth_following, latency_verdict, depth_verdict,
                edge_verdict, overall_verdict, score, metrics_json, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            ON CONFLICT(account) DO UPDATE SET
                worth_following = excluded.worth_following,
                latency_verdict = excluded.latency_verdict,
                depth_verdict = excluded.depth_verdict,
                edge_verdict = excluded.edge_verdict,
                overall_verdict = excluded.overall_verdict,
                score = excluded.score,
                metrics_json = excluded.metrics_json,
                updated_at = excluded.updated_at
            "#,
            params![
                score.account,
                score.worth_following,
                score.latency_verdict,
                score.depth_verdict,
                score.edge_verdict,
                score.overall_verdict,
                score.score.to_string(),
                score.metrics_json,
                Utc::now().to_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn latest_follow_depth_snapshot(
        &self,
        asset_id: &str,
    ) -> Result<Option<FollowDepthSnapshot>> {
        self.init()?;
        self.raw_connection()
            .query_row(
                r#"
                SELECT asset_id, best_bid, best_ask, spread, bid_depth, ask_depth, ofi, updated_at
                FROM clob_asset_features
                WHERE asset_id = ?1
                "#,
                params![asset_id],
                |row| {
                    Ok(FollowDepthSnapshot {
                        asset_id: row.get(0)?,
                        best_bid: parse_decimal(row.get(1)?),
                        best_ask: parse_decimal(row.get(2)?),
                        spread: parse_decimal(row.get(3)?),
                        bid_depth: parse_decimal(row.get(4)?),
                        ask_depth: parse_decimal(row.get(5)?),
                        ofi: parse_decimal(row.get(6)?),
                        updated_at: row.get(7)?,
                    })
                },
            )
            .optional()
            .map_err(Into::into)
    }

    pub fn follow_counts_for_wallet(&self, account: &str) -> Result<FollowCounts> {
        self.init()?;
        let account = account.to_ascii_lowercase();
        let events = self.raw_connection().query_row(
            "SELECT COUNT(*) FROM wallet_trade_events WHERE account = ?1",
            params![&account],
            |row| row.get::<_, i64>(0),
        )? as usize;
        let signals = self.raw_connection().query_row(
            "SELECT COUNT(*) FROM follow_signals WHERE account = ?1",
            params![&account],
            |row| row.get::<_, i64>(0),
        )? as usize;
        let paper_fills = count_where_joined_paper(self, &account)?;
        Ok(FollowCounts {
            events,
            signals,
            paper_fills,
        })
    }

    pub fn open_paper_follow_fills(
        &self,
        horizon_secs: i64,
        limit: usize,
    ) -> Result<Vec<OpenPaperFollowFill>> {
        self.init()?;
        let cutoff = (Utc::now() - Duration::seconds(horizon_secs)).to_rfc3339();
        let mut stmt = self.raw_connection().prepare(
            r#"
            SELECT p.paper_fill_id, s.market_id, s.side, p.entry_price, p.shares, p.entry_at
            FROM paper_follow_fills p
            JOIN follow_signals s ON s.signal_id = p.signal_id
            WHERE p.status = 'open' AND p.entry_at <= ?1
            ORDER BY p.entry_at ASC
            LIMIT ?2
            "#,
        )?;
        let rows = stmt.query_map(params![cutoff, limit], |row| {
            let entry_price: String = row.get(3)?;
            let shares: String = row.get(4)?;
            let entry_at: String = row.get(5)?;
            Ok(OpenPaperFollowFill {
                paper_fill_id: row.get(0)?,
                market_id: row.get(1)?,
                side: row.get(2)?,
                entry_price: entry_price.parse().map_err(parse_sql_error)?,
                shares: shares.parse().map_err(parse_sql_error)?,
                entry_at: DateTime::parse_from_rfc3339(&entry_at)
                    .map_err(parse_sql_error)?
                    .with_timezone(&Utc),
            })
        })?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn first_market_price_at_or_after(
        &self,
        market_id: &str,
        timestamp: DateTime<Utc>,
    ) -> Result<Option<MarketPricePoint>> {
        self.init()?;
        self.raw_connection()
            .query_row(
                r#"
                SELECT price, timestamp
                FROM fills
                WHERE market_id = ?1 AND timestamp >= ?2
                ORDER BY timestamp ASC, id ASC
                LIMIT 1
                "#,
                params![market_id, timestamp.to_rfc3339()],
                |row| {
                    let price: String = row.get(0)?;
                    let timestamp: String = row.get(1)?;
                    Ok(MarketPricePoint {
                        price: price.parse().map_err(parse_sql_error)?,
                        timestamp: DateTime::parse_from_rfc3339(&timestamp)
                            .map_err(parse_sql_error)?
                            .with_timezone(&Utc),
                    })
                },
            )
            .optional()
            .map_err(Into::into)
    }

    pub fn close_paper_follow_fill(
        &self,
        paper_fill_id: &str,
        exit_price: Decimal,
        exit_at: DateTime<Utc>,
        pnl: Decimal,
        pnl_bps: Decimal,
    ) -> Result<()> {
        self.init()?;
        self.raw_connection().execute(
            r#"
            UPDATE paper_follow_fills
            SET exit_price = ?2,
                exit_at = ?3,
                pnl = ?4,
                pnl_bps = ?5,
                status = 'closed'
            WHERE paper_fill_id = ?1
            "#,
            params![
                paper_fill_id,
                exit_price.to_string(),
                exit_at.to_rfc3339(),
                pnl.to_string(),
                pnl_bps.to_string(),
            ],
        )?;
        Ok(())
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct FollowCounts {
    pub events: usize,
    pub signals: usize,
    pub paper_fills: usize,
}

fn parse_decimal(raw: Option<String>) -> Option<Decimal> {
    raw.and_then(|value| value.parse::<Decimal>().ok())
}

fn count_where_joined_paper(storage: &Storage, account: &str) -> Result<usize> {
    Ok(storage.raw_connection().query_row(
        r#"
        SELECT COUNT(*)
        FROM paper_follow_fills p
        JOIN follow_signals s ON s.signal_id = p.signal_id
        WHERE s.account = ?1
        "#,
        params![account],
        |row| row.get::<_, i64>(0),
    )? as usize)
}

fn parse_sql_error(error: impl std::error::Error + Send + Sync + 'static) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(error))
}
