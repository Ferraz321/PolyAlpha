CREATE TABLE IF NOT EXISTS raw_clob_events
(
    channel LowCardinality(String),
    event_type LowCardinality(String),
    asset_id String,
    payload String,
    received_at DateTime64(3, 'UTC'),
    stable_key String,
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(received_at)
ORDER BY (asset_id, received_at, stable_key);

CREATE TABLE IF NOT EXISTS clob_asset_features
(
    asset_id String,
    market String,
    best_bid Decimal(18, 8),
    best_ask Decimal(18, 8),
    spread Decimal(18, 8),
    bid_depth Decimal(18, 8),
    ask_depth Decimal(18, 8),
    ofi Decimal(18, 8),
    last_trade_price Decimal(18, 8),
    last_trade_size Decimal(18, 8),
    last_trade_side LowCardinality(String),
    last_event_type LowCardinality(String),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
PARTITION BY toYYYYMM(updated_at)
ORDER BY (asset_id, updated_at);

CREATE TABLE IF NOT EXISTS wallet_microstructure_metrics
(
    account String,
    observed_fills UInt64,
    avg_spread Decimal(18, 8),
    avg_ofi Decimal(18, 8),
    favorable_ofi_rate Decimal(18, 8),
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (account, updated_at);
