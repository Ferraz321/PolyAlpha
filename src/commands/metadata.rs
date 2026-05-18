use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Url;
use rusqlite::{Connection, params};
use serde::Deserialize;
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

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct GammaMarket {
    condition_id: Option<String>,
    slug: Option<String>,
    event_slug: Option<String>,
    category: Option<String>,
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
        let tokens = markets.iter().flat_map(market_tokens).collect::<Vec<_>>();
        inserted += upsert_tokens(&conn, &tokens)?;
        offset += args.limit;
    }

    println!("metadata: upserted_token_rows={inserted}");
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
