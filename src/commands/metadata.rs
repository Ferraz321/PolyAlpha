use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Url;
use rusqlite::{Connection, params};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::app::cli::SyncMetadataArgs;

#[derive(Debug)]
struct TokenMetadata {
    token_id: String,
    condition_id: Option<String>,
    market_slug: Option<String>,
    event_slug: Option<String>,
    sector: Option<String>,
    outcome: Option<String>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct GammaMarket {
    condition_id: Option<String>,
    slug: Option<String>,
    event_slug: Option<String>,
    category: Option<String>,
    question: Option<String>,
    end_date: Option<String>,
    active: Option<bool>,
    closed: Option<bool>,
    clob_token_ids: Option<Value>,
    outcomes: Option<Value>,
}

pub async fn sync_metadata(args: SyncMetadataArgs) -> Result<()> {
    if let Some(parent) = args.db.parent() {
        std::fs::create_dir_all(parent).context("failed to create db directory")?;
    }
    let conn = Connection::open(&args.db).context("failed to open sqlite database")?;
    conn.execute_batch(include_str!("../../sql/schema.sql"))?;
    let mut offset = 0usize;
    let mut inserted = 0usize;

    while offset <= args.max_offset {
        let markets = fetch_markets(&args.gamma_base_url, args.limit, offset).await?;
        if markets.is_empty() {
            break;
        }
        inserted += upsert_markets(&conn, &markets)?;
        let tokens = markets.iter().flat_map(market_tokens).collect::<Vec<_>>();
        inserted += upsert_tokens(&conn, &tokens)?;
        inserted += upsert_outcomes(&conn, &tokens)?;
        offset += args.limit;
    }

    println!("metadata: upserted_rows={inserted}");
    Ok(())
}

async fn fetch_markets(base_url: &str, limit: usize, offset: usize) -> Result<Vec<GammaMarket>> {
    let mut url = Url::parse(base_url)?.join("markets")?;
    url.query_pairs_mut()
        .append_pair("limit", &limit.to_string())
        .append_pair("offset", &offset.to_string());
    reqwest::get(url)
        .await?
        .error_for_status()?
        .json::<Vec<GammaMarket>>()
        .await
        .context("failed to decode gamma markets")
}

fn market_tokens(market: &GammaMarket) -> Vec<TokenMetadata> {
    let tokens = string_vec(market.clob_token_ids.as_ref());
    let outcomes = string_vec(market.outcomes.as_ref());
    tokens
        .into_iter()
        .enumerate()
        .map(|(index, token_id)| TokenMetadata {
            token_id,
            condition_id: market.condition_id.clone(),
            market_slug: market.slug.clone(),
            event_slug: market.event_slug.clone(),
            sector: market.category.clone(),
            outcome: outcomes.get(index).cloned(),
        })
        .collect()
}

fn string_vec(value: Option<&Value>) -> Vec<String> {
    match value {
        Some(Value::Array(items)) => items
            .iter()
            .filter_map(|item| item.as_str().map(ToString::to_string))
            .collect(),
        Some(Value::String(text)) => serde_json::from_str::<Vec<String>>(text).unwrap_or_default(),
        _ => Vec::new(),
    }
}

fn upsert_tokens(conn: &Connection, tokens: &[TokenMetadata]) -> Result<usize> {
    let updated_at = Utc::now().to_rfc3339();
    let mut changed = 0usize;
    for token in tokens {
        changed += conn.execute(
            r#"
            INSERT INTO market_tokens (
                token_id, condition_id, market_slug, event_slug, sector, outcome, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
            ON CONFLICT(token_id) DO UPDATE SET
                condition_id = excluded.condition_id,
                market_slug = excluded.market_slug,
                event_slug = excluded.event_slug,
                sector = excluded.sector,
                outcome = excluded.outcome,
                updated_at = excluded.updated_at
            "#,
            params![
                token.token_id,
                token.condition_id,
                token.market_slug,
                token.event_slug,
                token.sector,
                token.outcome,
                updated_at,
            ],
        )?;
    }
    Ok(changed)
}

fn upsert_markets(conn: &Connection, markets: &[GammaMarket]) -> Result<usize> {
    let updated_at = Utc::now().to_rfc3339();
    let mut changed = 0usize;
    for market in markets {
        let Some(market_id) = market_id(market) else {
            continue;
        };
        changed += conn.execute(
            r#"
            INSERT INTO markets (
                market_id, condition_id, market_slug, event_slug, sector, question,
                resolution_time, status, raw_json, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
            ON CONFLICT(market_id) DO UPDATE SET
                condition_id = excluded.condition_id,
                market_slug = excluded.market_slug,
                event_slug = excluded.event_slug,
                sector = excluded.sector,
                question = excluded.question,
                resolution_time = excluded.resolution_time,
                status = excluded.status,
                raw_json = excluded.raw_json,
                updated_at = excluded.updated_at
            "#,
            params![
                market_id,
                market.condition_id,
                market.slug,
                market.event_slug,
                market.category,
                market.question,
                market.end_date,
                market_status(market),
                serde_json::to_string(market)?,
                updated_at,
            ],
        )?;
    }
    Ok(changed)
}

fn upsert_outcomes(conn: &Connection, tokens: &[TokenMetadata]) -> Result<usize> {
    let updated_at = Utc::now().to_rfc3339();
    let mut changed = 0usize;
    for token in tokens {
        let Some(market_id) = token
            .condition_id
            .clone()
            .or_else(|| token.market_slug.clone())
            .or_else(|| token.event_slug.clone())
        else {
            continue;
        };
        changed += conn.execute(
            r#"
            INSERT INTO outcomes (
                outcome_id, market_id, token_id, label, resolution_status, updated_at
            )
            VALUES (?1, ?2, ?3, ?4, 'unknown', ?5)
            ON CONFLICT(outcome_id) DO UPDATE SET
                market_id = excluded.market_id,
                token_id = excluded.token_id,
                label = excluded.label,
                updated_at = excluded.updated_at
            "#,
            params![
                token.token_id,
                market_id,
                token.token_id,
                token.outcome,
                updated_at,
            ],
        )?;
    }
    Ok(changed)
}

fn market_id(market: &GammaMarket) -> Option<String> {
    market
        .condition_id
        .clone()
        .or_else(|| market.slug.clone())
        .or_else(|| market.event_slug.clone())
}

fn market_status(market: &GammaMarket) -> String {
    if market.closed == Some(true) {
        "closed".to_string()
    } else if market.active == Some(true) {
        "active".to_string()
    } else {
        "unknown".to_string()
    }
}
