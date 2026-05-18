use chrono::{DateTime, Utc};
use rust_decimal::Decimal;
use serde::{Deserialize, Serialize};
use strum::{Display, EnumString};

#[derive(Debug, Clone, Copy, Deserialize, Serialize, Display, EnumString, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[strum(serialize_all = "snake_case")]
pub enum TradeSide {
    Buy,
    Sell,
}

#[derive(Debug, Clone, Copy, Deserialize, Serialize, Display, EnumString, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
#[strum(serialize_all = "snake_case")]
pub enum LiquidityRole {
    Maker,
    Taker,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct FillEvent {
    pub account: String,
    pub market_id: String,
    pub condition_id: Option<String>,
    pub event_slug: Option<String>,
    pub sector: Option<String>,
    pub side: TradeSide,
    pub role: LiquidityRole,
    #[serde(with = "rust_decimal::serde::str")]
    pub price: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub shares: Decimal,
    pub timestamp: DateTime<Utc>,
    pub tx_hash: Option<String>,
    pub order_hash: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MarketClosedLoop {
    pub account: String,
    pub market_id: String,
    #[serde(with = "rust_decimal::serde::str")]
    pub buy_shares: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub sell_shares: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub buy_notional: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub sell_notional: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub pnl: Decimal,
    pub first_trade_at: DateTime<Utc>,
    pub last_trade_at: DateTime<Utc>,
    pub sectors: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct AccountMetrics {
    pub account: String,
    #[serde(with = "rust_decimal::serde::str")]
    pub total_volume: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub avg_trade_size: Decimal,
    pub trade_count: usize,
    pub distinct_markets: usize,
    pub closed_markets: usize,
    #[serde(with = "rust_decimal::serde::str")]
    pub total_pnl: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub win_rate: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub profit_loss_ratio: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub expectancy: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub max_single_market_pnl_share: Decimal,
    #[serde(with = "rust_decimal::serde::str")]
    pub maker_ratio: Decimal,
    pub dominant_sector: Option<String>,
    #[serde(with = "rust_decimal::serde::str")]
    pub sector_concentration: Decimal,
}
