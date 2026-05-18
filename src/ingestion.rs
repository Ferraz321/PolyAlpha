use anyhow::{Context, Result, bail};
use chrono::{TimeZone, Utc};
use reqwest::{StatusCode, Url};
use rust_decimal::Decimal;
use serde::Deserialize;
use serde_json::Value;
use std::str::FromStr;

use crate::model::{FillEvent, LiquidityRole, TradeSide};

#[derive(Debug, Clone)]
pub struct DataApiClient {
    base_url: Url,
    http: reqwest::Client,
}

impl DataApiClient {
    pub fn new(base_url: &str) -> Result<Self> {
        Ok(Self {
            base_url: Url::parse(base_url).context("invalid data api base url")?,
            http: reqwest::Client::new(),
        })
    }

    pub async fn fetch_trades(&self, limit: usize, offset: usize) -> Result<Vec<DataApiTrade>> {
        let mut url = self
            .base_url
            .join("trades")
            .context("failed to build trades url")?;
        url.query_pairs_mut()
            .append_pair("limit", &limit.to_string())
            .append_pair("offset", &offset.to_string());

        let response = self
            .http
            .get(url)
            .send()
            .await
            .context("data api trades request failed")?;

        if response.status() == StatusCode::BAD_REQUEST && offset > 0 {
            tracing::warn!(offset, "data api rejected page; treating as pagination end");
            return Ok(Vec::new());
        }
        let response = response
            .error_for_status()
            .context("data api trades returned error status")?;

        response
            .json::<Vec<DataApiTrade>>()
            .await
            .context("failed to decode data api trades")
    }
}

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DataApiTrade {
    pub proxy_wallet: String,
    pub side: String,
    pub asset: Option<String>,
    pub condition_id: String,
    pub size: Value,
    pub price: Value,
    pub timestamp: i64,
    pub slug: Option<String>,
    pub event_slug: Option<String>,
    pub outcome: Option<String>,
    pub transaction_hash: Option<String>,
}

impl DataApiTrade {
    pub fn stable_key(&self) -> String {
        format!(
            "{}:{}:{}:{}:{}:{}",
            self.transaction_hash.as_deref().unwrap_or(""),
            self.proxy_wallet,
            self.condition_id,
            self.asset.as_deref().unwrap_or(""),
            self.side,
            self.timestamp
        )
    }

    pub fn into_fill_event(self) -> Result<FillEvent> {
        let side = match self.side.to_ascii_uppercase().as_str() {
            "BUY" => TradeSide::Buy,
            "SELL" => TradeSide::Sell,
            other => bail!("unsupported trade side: {other}"),
        };

        let timestamp = Utc
            .timestamp_opt(self.timestamp, 0)
            .single()
            .context("invalid unix timestamp")?;

        Ok(FillEvent {
            account: self.proxy_wallet,
            market_id: self
                .asset
                .clone()
                .unwrap_or_else(|| self.condition_id.clone()),
            condition_id: Some(self.condition_id),
            event_slug: self.event_slug.or(self.slug),
            sector: None,
            side,
            role: LiquidityRole::Taker,
            price: decimal_from_value(&self.price)?,
            shares: decimal_from_value(&self.size)?,
            timestamp,
            tx_hash: self.transaction_hash,
            order_hash: None,
        })
    }
}

fn decimal_from_value(value: &Value) -> Result<Decimal> {
    match value {
        Value::String(value) => Decimal::from_str(value).context("invalid decimal string"),
        Value::Number(value) => Decimal::from_str(&value.to_string()).context("invalid decimal"),
        other => bail!("expected decimal string or number, got {other}"),
    }
}
