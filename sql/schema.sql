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

CREATE TABLE IF NOT EXISTS markets (
    market_id TEXT PRIMARY KEY,
    condition_id TEXT,
    market_slug TEXT,
    event_slug TEXT,
    sector TEXT,
    question TEXT,
    resolution_time TEXT,
    status TEXT NOT NULL DEFAULT 'unknown',
    raw_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_markets_event_slug ON markets(event_slug);
CREATE INDEX IF NOT EXISTS idx_markets_sector ON markets(sector);
CREATE INDEX IF NOT EXISTS idx_markets_resolution_time ON markets(resolution_time);

CREATE TABLE IF NOT EXISTS outcomes (
    outcome_id TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    token_id TEXT,
    label TEXT,
    resolved_value TEXT,
    resolution_status TEXT NOT NULL DEFAULT 'unknown',
    updated_at TEXT NOT NULL,
    FOREIGN KEY(market_id) REFERENCES markets(market_id)
);

CREATE INDEX IF NOT EXISTS idx_outcomes_market ON outcomes(market_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_token ON outcomes(token_id);

CREATE TABLE IF NOT EXISTS positions (
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    shares TEXT NOT NULL,
    avg_price TEXT NOT NULL,
    cost_basis TEXT NOT NULL,
    realized_pnl TEXT NOT NULL DEFAULT '0',
    unrealized_pnl TEXT NOT NULL DEFAULT '0',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(account, market_id, outcome_id)
);

CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account);
CREATE INDEX IF NOT EXISTS idx_positions_market ON positions(market_id);

CREATE TABLE IF NOT EXISTS wallet_pnl (
    account TEXT NOT NULL,
    scope TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    unrealized_pnl TEXT NOT NULL DEFAULT '0',
    trade_count INTEGER NOT NULL,
    market_count INTEGER NOT NULL,
    audit_status TEXT NOT NULL DEFAULT 'estimated',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(account, scope)
);

CREATE TABLE IF NOT EXISTS settlement_events (
    event_id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    event_type TEXT NOT NULL,
    amount TEXT NOT NULL DEFAULT '0',
    payout TEXT NOT NULL DEFAULT '0',
    settlement_price TEXT,
    tx_hash TEXT,
    log_index INTEGER,
    block_number INTEGER,
    timestamp TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_settlement_events_account ON settlement_events(account);
CREATE INDEX IF NOT EXISTS idx_settlement_events_market ON settlement_events(market_id);
CREATE INDEX IF NOT EXISTS idx_settlement_events_timestamp ON settlement_events(timestamp);

CREATE TABLE IF NOT EXISTS wallet_clusters (
    cluster_id TEXT NOT NULL,
    account TEXT NOT NULL,
    method TEXT NOT NULL,
    label TEXT,
    score TEXT,
    features_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    PRIMARY KEY(cluster_id, account)
);

CREATE INDEX IF NOT EXISTS idx_wallet_clusters_account ON wallet_clusters(account);
CREATE INDEX IF NOT EXISTS idx_wallet_clusters_method ON wallet_clusters(method);

CREATE TABLE IF NOT EXISTS factor_values (
    factor_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    market_id TEXT,
    timestamp TEXT NOT NULL,
    value TEXT,
    source TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(factor_id, entity_type, entity_id, timestamp, version)
);

CREATE INDEX IF NOT EXISTS idx_factor_values_factor ON factor_values(factor_id);
CREATE INDEX IF NOT EXISTS idx_factor_values_entity ON factor_values(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_factor_values_market ON factor_values(market_id);

CREATE TABLE IF NOT EXISTS factor_candidates (
    factor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'candidate',
    priority INTEGER NOT NULL DEFAULT 3,
    required_data TEXT NOT NULL DEFAULT 'factor_table',
    owner_module TEXT,
    hypothesis TEXT,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_factor_candidates_state ON factor_candidates(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_factor_candidates_priority ON factor_candidates(priority);

CREATE TABLE IF NOT EXISTS factor_validations (
    validation_id TEXT PRIMARY KEY,
    factor_id TEXT NOT NULL,
    method TEXT NOT NULL,
    sample_start TEXT,
    sample_end TEXT,
    in_sample_score TEXT,
    out_of_sample_score TEXT,
    negative_control_score TEXT,
    stability_score TEXT,
    slippage_bps TEXT,
    capacity_usd TEXT,
    verdict TEXT NOT NULL DEFAULT 'pending',
    report_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(factor_id) REFERENCES factor_candidates(factor_id)
);

CREATE INDEX IF NOT EXISTS idx_factor_validations_factor ON factor_validations(factor_id);
CREATE INDEX IF NOT EXISTS idx_factor_validations_verdict ON factor_validations(verdict);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft',
    config_json TEXT NOT NULL,
    source_factors_json TEXT NOT NULL DEFAULT '[]',
    risk_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategies_state ON strategies(lifecycle_state);

CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    account TEXT,
    market_id TEXT,
    outcome_id TEXT,
    signal_type TEXT NOT NULL,
    score TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    emitted_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    FOREIGN KEY(strategy_id) REFERENCES strategies(strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy_id);
CREATE INDEX IF NOT EXISTS idx_signals_market ON signals(market_id);
CREATE INDEX IF NOT EXISTS idx_signals_emitted ON signals(emitted_at);
