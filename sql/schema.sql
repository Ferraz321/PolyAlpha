CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    condition_id TEXT,
    event_slug TEXT,
    sector TEXT,
    side TEXT NOT NULL,
    role TEXT NOT NULL,
    price TEXT NOT NULL,
    shares TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    tx_hash TEXT,
    order_hash TEXT,
    stable_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fills_account ON fills(account);
CREATE INDEX IF NOT EXISTS idx_fills_timestamp ON fills(timestamp);
CREATE INDEX IF NOT EXISTS idx_fills_market ON fills(market_id);

CREATE TABLE IF NOT EXISTS wallets (
    account TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    total_trades INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS dirty_wallets (
    account TEXT PRIMARY KEY,
    reason TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_metrics (
    account TEXT PRIMARY KEY,
    metrics_json TEXT NOT NULL,
    classification_json TEXT NOT NULL,
    passed_funnel INTEGER NOT NULL,
    failed_reasons_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matched_accounts (
    account TEXT PRIMARY KEY,
    report_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_watchlist (
    account TEXT PRIMARY KEY,
    label TEXT,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scanner_state (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_evm_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_address TEXT NOT NULL,
    block_number INTEGER NOT NULL,
    transaction_hash TEXT NOT NULL,
    log_index INTEGER NOT NULL,
    topic0 TEXT,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(transaction_hash, log_index)
);

CREATE TABLE IF NOT EXISTS raw_clob_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    event_type TEXT,
    asset_id TEXT,
    payload TEXT NOT NULL,
    received_at TEXT NOT NULL,
    stable_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_clob_events_asset ON raw_clob_events(asset_id);
CREATE INDEX IF NOT EXISTS idx_raw_clob_events_received ON raw_clob_events(received_at);

CREATE TABLE IF NOT EXISTS clob_asset_features (
    asset_id TEXT PRIMARY KEY,
    market TEXT,
    best_bid TEXT,
    best_ask TEXT,
    spread TEXT,
    bid_depth TEXT,
    ask_depth TEXT,
    ofi TEXT,
    last_trade_price TEXT,
    last_trade_size TEXT,
    last_trade_side TEXT,
    last_event_type TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wallet_microstructure_metrics (
    account TEXT PRIMARY KEY,
    observed_fills INTEGER NOT NULL,
    avg_spread TEXT NOT NULL,
    avg_ofi TEXT NOT NULL,
    favorable_ofi_rate TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_tokens (
    token_id TEXT PRIMARY KEY,
    condition_id TEXT,
    market_slug TEXT,
    event_slug TEXT,
    sector TEXT,
    outcome TEXT,
    updated_at TEXT NOT NULL
);
