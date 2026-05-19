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

CREATE TABLE IF NOT EXISTS wallet_trade_events (
    event_id TEXT PRIMARY KEY,
    fill_id BIGINT UNIQUE,
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    side TEXT NOT NULL,
    price NUMERIC NOT NULL,
    shares NUMERIC NOT NULL,
    source_timestamp TIMESTAMPTZ NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    latency_ms BIGINT NOT NULL,
    source TEXT NOT NULL DEFAULT 'data_api',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pg_wallet_trade_events_account ON wallet_trade_events(account);
CREATE INDEX IF NOT EXISTS idx_pg_wallet_trade_events_market ON wallet_trade_events(market_id);
CREATE INDEX IF NOT EXISTS idx_pg_wallet_trade_events_observed ON wallet_trade_events(observed_at);

CREATE TABLE IF NOT EXISTS follow_signals (
    signal_id TEXT PRIMARY KEY,
    wallet_event_id TEXT NOT NULL REFERENCES wallet_trade_events(event_id),
    account TEXT NOT NULL,
    market_id TEXT NOT NULL,
    outcome_id TEXT,
    side TEXT NOT NULL,
    target_price NUMERIC NOT NULL,
    copied_shares NUMERIC NOT NULL,
    max_notional NUMERIC NOT NULL,
    score NUMERIC NOT NULL,
    verdict TEXT NOT NULL,
    reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    emitted_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'paper'
);

CREATE INDEX IF NOT EXISTS idx_pg_follow_signals_account ON follow_signals(account);
CREATE INDEX IF NOT EXISTS idx_pg_follow_signals_market ON follow_signals(market_id);
CREATE INDEX IF NOT EXISTS idx_pg_follow_signals_verdict ON follow_signals(verdict);

CREATE TABLE IF NOT EXISTS paper_follow_fills (
    paper_fill_id TEXT PRIMARY KEY,
    signal_id TEXT NOT NULL REFERENCES follow_signals(signal_id),
    wallet_event_id TEXT NOT NULL REFERENCES wallet_trade_events(event_id),
    entry_price NUMERIC NOT NULL,
    shares NUMERIC NOT NULL,
    notional NUMERIC NOT NULL,
    slippage_bps NUMERIC NOT NULL,
    depth_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    depth_status TEXT NOT NULL,
    entry_at TIMESTAMPTZ NOT NULL,
    exit_price NUMERIC,
    exit_at TIMESTAMPTZ,
    pnl NUMERIC,
    pnl_bps NUMERIC,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pg_paper_follow_fills_signal ON paper_follow_fills(signal_id);
CREATE INDEX IF NOT EXISTS idx_pg_paper_follow_fills_status ON paper_follow_fills(status);

CREATE TABLE IF NOT EXISTS wallet_follow_scores (
    account TEXT PRIMARY KEY,
    worth_following TEXT NOT NULL,
    latency_verdict TEXT NOT NULL,
    depth_verdict TEXT NOT NULL,
    edge_verdict TEXT NOT NULL,
    overall_verdict TEXT NOT NULL,
    score NUMERIC NOT NULL,
    metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pg_wallet_follow_scores_overall ON wallet_follow_scores(overall_verdict);
