CREATE TABLE IF NOT EXISTS settlement_events (
    event_id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    event_type TEXT NOT NULL,
    amount NUMERIC NOT NULL DEFAULT 0,
    payout NUMERIC NOT NULL DEFAULT 0,
    settlement_price NUMERIC,
    tx_hash TEXT,
    log_index BIGINT,
    block_number BIGINT,
    timestamp TIMESTAMPTZ NOT NULL,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pg_settlement_events_account ON settlement_events(account);
CREATE INDEX IF NOT EXISTS idx_pg_settlement_events_market ON settlement_events(market_id);
CREATE INDEX IF NOT EXISTS idx_pg_settlement_events_timestamp ON settlement_events(timestamp);

CREATE TABLE IF NOT EXISTS wallet_pnl (
    account TEXT NOT NULL,
    scope TEXT NOT NULL,
    realized_pnl NUMERIC NOT NULL,
    unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
    trade_count BIGINT NOT NULL,
    market_count BIGINT NOT NULL,
    audit_status TEXT NOT NULL DEFAULT 'estimated',
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(account, scope)
);

CREATE TABLE IF NOT EXISTS positions (
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    shares NUMERIC NOT NULL,
    avg_price NUMERIC NOT NULL,
    cost_basis NUMERIC NOT NULL,
    realized_pnl NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(account, market_id, outcome_id)
);

CREATE TABLE IF NOT EXISTS factor_candidates (
    factor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'candidate',
    priority INTEGER NOT NULL DEFAULT 3,
    required_data TEXT NOT NULL DEFAULT 'factor_table',
    owner_module TEXT,
    hypothesis TEXT,
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS factor_validations (
    validation_id TEXT PRIMARY KEY,
    factor_id TEXT NOT NULL REFERENCES factor_candidates(factor_id),
    method TEXT NOT NULL,
    sample_start TIMESTAMPTZ,
    sample_end TIMESTAMPTZ,
    in_sample_score NUMERIC,
    out_of_sample_score NUMERIC,
    negative_control_score NUMERIC,
    stability_score NUMERIC,
    slippage_bps NUMERIC,
    capacity_usd NUMERIC,
    verdict TEXT NOT NULL DEFAULT 'pending',
    report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft',
    config_json JSONB NOT NULL,
    source_factors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    signal_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id),
    account TEXT,
    market_id TEXT,
    outcome_id TEXT,
    signal_type TEXT NOT NULL,
    score NUMERIC NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    emitted_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'new'
);
