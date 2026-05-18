use anyhow::Result;
use oktrader_alpha::storage::Storage;

use crate::app::cli::DbArgs;

pub fn research_status(args: DbArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    let db = storage.stats()?;
    let research = storage.research_stats()?;

    println!("polyedge research status: db={}", args.db.display());
    println!(
        "data: fills={}, wallets={}, raw_evm_logs={}, raw_clob_events={}, clob_asset_features={}",
        db.fills, db.wallets, db.raw_evm_logs, db.raw_clob_events, db.clob_asset_features
    );
    println!(
        "wallet_intelligence: account_metrics={}, matched_accounts={}, wallet_pnl={}, positions={}, settlement_events={}, clusters={}",
        db.account_metrics,
        db.matched_accounts,
        research.wallet_pnl,
        research.positions,
        research.settlement_events,
        research.wallet_clusters
    );
    println!(
        "market_context: markets={}, outcomes={}, market_tokens={}",
        research.markets, research.outcomes, research.market_tokens
    );
    println!(
        "factor_lifecycle: factor_values={}, candidates={}, validations={}",
        research.factor_values, research.factor_candidates, research.factor_validations
    );
    println!(
        "strategy_signal: strategies={}, signals={}",
        research.strategies, research.signals
    );
    Ok(())
}
