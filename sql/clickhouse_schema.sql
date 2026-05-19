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

CREATE TABLE IF NOT EXISTS wallet_trade_events
(
    event_id String,
    fill_id Int64,
    account String,
    market_id String,
    outcome_id String,
    side LowCardinality(String),
    price Decimal(18, 8),
    shares Decimal(18, 8),
    source_timestamp DateTime64(3, 'UTC'),
    observed_at DateTime64(3, 'UTC'),
    received_at DateTime64(3, 'UTC'),
    latency_ms Int64,
    source LowCardinality(String),
    payload_json String,
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(observed_at)
ORDER BY (account, observed_at, event_id);

CREATE TABLE IF NOT EXISTS follow_signals
(
    signal_id String,
    wallet_event_id String,
    account String,
    market_id String,
    outcome_id String,
    side LowCardinality(String),
    target_price Decimal(18, 8),
    copied_shares Decimal(18, 8),
    max_notional Decimal(18, 8),
    score Decimal(18, 8),
    verdict LowCardinality(String),
    reasons_json String,
    emitted_at DateTime64(3, 'UTC'),
    status LowCardinality(String)
)
ENGINE = ReplacingMergeTree(emitted_at)
PARTITION BY toYYYYMM(emitted_at)
ORDER BY (account, market_id, emitted_at, signal_id);

CREATE TABLE IF NOT EXISTS paper_follow_fills
(
    paper_fill_id String,
    signal_id String,
    wallet_event_id String,
    entry_price Decimal(18, 8),
    shares Decimal(18, 8),
    notional Decimal(18, 8),
    slippage_bps Decimal(18, 8),
    depth_snapshot_json String,
    depth_status LowCardinality(String),
    entry_at DateTime64(3, 'UTC'),
    exit_price Nullable(Decimal(18, 8)),
    exit_at Nullable(DateTime64(3, 'UTC')),
    pnl Nullable(Decimal(18, 8)),
    pnl_bps Nullable(Decimal(18, 8)),
    status LowCardinality(String),
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(entry_at)
ORDER BY (status, entry_at, paper_fill_id);

CREATE TABLE IF NOT EXISTS wallet_follow_scores
(
    account String,
    worth_following LowCardinality(String),
    latency_verdict LowCardinality(String),
    depth_verdict LowCardinality(String),
    edge_verdict LowCardinality(String),
    overall_verdict LowCardinality(String),
    score Decimal(18, 8),
    metrics_json String,
    updated_at DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (overall_verdict, account);
