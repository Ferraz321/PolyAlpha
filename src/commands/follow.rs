use std::time::Duration;

use anyhow::Result;
use chrono::Utc;
use oktrader_alpha::model::TradeSide;
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_alerts::{AlertMode, StoredFill};
use oktrader_alpha::storage_follow::{
    FollowDepthSnapshot, FollowSignalRecord, PaperFollowFillRecord, WalletFollowScoreRecord,
    WalletTradeEventRecord,
};
use rust_decimal::Decimal;
use rust_decimal_macros::dec;
use serde_json::json;

use crate::app::cli::{FollowClosePaperArgs, FollowWatchArgs};

const FOLLOW_CURSOR: &str = "follow_watch.last_fill_id";

pub async fn follow_watch(args: FollowWatchArgs) -> Result<()> {
    loop {
        let storage = Storage::open(&args.db)?;
        let mut cursor = storage
            .get_state(FOLLOW_CURSOR)?
            .and_then(|value| value.parse::<i64>().ok())
            .unwrap_or(0);
        if cursor == 0 {
            cursor = storage.max_fill_id()?;
            storage.set_state(FOLLOW_CURSOR, &cursor.to_string())?;
            println!("follow-watch: initialized cursor at fill_id={cursor}");
        }

        let fills = storage.fills_after(cursor, args.limit, AlertMode::Watchlist)?;
        let mut observed = 0usize;
        let mut paper = 0usize;
        let mut blocked = 0usize;
        for stored in &fills {
            let action = build_follow_action(&storage, stored, &args)?;
            storage.upsert_wallet_trade_event(&action.event)?;
            storage.insert_follow_signal(&action.signal)?;
            if let Some(paper_fill) = action.paper_fill.as_ref() {
                storage.insert_paper_follow_fill(paper_fill)?;
                paper += 1;
            } else {
                blocked += 1;
            }
            storage.upsert_wallet_follow_score(&action.score)?;
            cursor = stored.id;
            observed += 1;
        }
        if observed > 0 {
            storage.set_state(FOLLOW_CURSOR, &cursor.to_string())?;
        }
        println!(
            "follow-watch: observed={}, paper_fills={}, blocked={}, db={}",
            observed,
            paper,
            blocked,
            args.db.display()
        );

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

pub fn follow_close_paper(args: FollowClosePaperArgs) -> Result<()> {
    let storage = Storage::open(&args.db)?;
    let open = storage.open_paper_follow_fills(args.horizon_secs, args.limit)?;
    let mut closed = 0usize;
    let mut missing_exit = 0usize;
    for paper in &open {
        let exit_after = paper.entry_at + chrono::Duration::seconds(args.horizon_secs);
        let Some(exit) = storage.first_market_price_at_or_after(&paper.market_id, exit_after)?
        else {
            missing_exit += 1;
            continue;
        };
        let pnl_per_share = if paper.side == "buy" {
            exit.price - paper.entry_price
        } else {
            paper.entry_price - exit.price
        };
        let pnl = pnl_per_share * paper.shares;
        let entry_notional = paper.entry_price * paper.shares;
        let pnl_bps = if entry_notional == Decimal::ZERO {
            Decimal::ZERO
        } else {
            pnl / entry_notional * dec!(10000)
        };
        storage.close_paper_follow_fill(
            &paper.paper_fill_id,
            exit.price,
            exit.timestamp,
            pnl,
            pnl_bps,
        )?;
        closed += 1;
    }
    println!(
        "follow-close-paper: eligible={}, closed={}, missing_exit={}, db={}",
        open.len(),
        closed,
        missing_exit,
        args.db.display()
    );
    Ok(())
}

struct FollowAction {
    event: WalletTradeEventRecord,
    signal: FollowSignalRecord,
    paper_fill: Option<PaperFollowFillRecord>,
    score: WalletFollowScoreRecord,
}

fn build_follow_action(
    storage: &Storage,
    stored: &StoredFill,
    args: &FollowWatchArgs,
) -> Result<FollowAction> {
    let fill = &stored.fill;
    let now = Utc::now();
    let latency_ms = (now - fill.timestamp).num_milliseconds().max(0);
    let event_id = format!("wallet_event:fill:{}", stored.id);
    let signal_id = format!("follow_signal:fill:{}", stored.id);
    let paper_fill_id = format!("paper_follow:fill:{}", stored.id);
    let side = fill.side.to_string();
    let wallet_notional = fill.price * fill.shares;
    let copied_notional = std::cmp::min(wallet_notional * args.copy_fraction, args.max_notional);
    let copied_shares = if fill.price > Decimal::ZERO {
        copied_notional / fill.price
    } else {
        Decimal::ZERO
    };
    let depth = latest_depth_for_fill(storage, stored)?;
    let mut reasons = Vec::<String>::new();
    if latency_ms > args.max_latency_secs * 1000 {
        reasons.push(format!(
            "latency_ms {latency_ms} exceeds max_latency_ms {}",
            args.max_latency_secs * 1000
        ));
    }
    if copied_shares <= Decimal::ZERO {
        reasons.push("copied_shares is zero".to_string());
    }
    let depth_status = depth_status(
        fill.side,
        copied_shares,
        args.min_depth_shares,
        depth.as_ref(),
    );
    if depth_status != "pass" {
        reasons.push(format!("depth_status={depth_status}"));
    }
    let verdict = if reasons.is_empty() {
        "paper"
    } else {
        "blocked"
    };
    let emitted_at = now.to_rfc3339();
    let entry_price = apply_slippage(fill.price, fill.side, args.slippage_bps);
    let notional = entry_price * copied_shares;
    let depth_snapshot_json = serde_json::to_string(&depth)?;
    let event = WalletTradeEventRecord {
        event_id: event_id.clone(),
        fill_id: Some(stored.id),
        account: fill.account.to_ascii_lowercase(),
        market_id: fill.market_id.clone(),
        outcome_id: fill.condition_id.clone(),
        side: side.clone(),
        price: fill.price,
        shares: fill.shares,
        source_timestamp: fill.timestamp.to_rfc3339(),
        observed_at: emitted_at.clone(),
        received_at: emitted_at.clone(),
        latency_ms,
        source: "data_api_watchlist".to_string(),
        payload_json: json!({
            "fill_id": stored.id,
            "event_slug": fill.event_slug,
            "sector": fill.sector,
            "tx_hash": fill.tx_hash,
            "order_hash": fill.order_hash,
        })
        .to_string(),
    };
    let signal = FollowSignalRecord {
        signal_id: signal_id.clone(),
        wallet_event_id: event_id.clone(),
        account: fill.account.to_ascii_lowercase(),
        market_id: fill.market_id.clone(),
        outcome_id: fill.condition_id.clone(),
        side,
        target_price: entry_price,
        copied_shares,
        max_notional: args.max_notional,
        score: score_for(verdict, latency_ms, args.max_latency_secs),
        verdict: verdict.to_string(),
        reasons_json: serde_json::to_string(&reasons)?,
        emitted_at: emitted_at.clone(),
        status: "paper".to_string(),
    };
    let paper_fill = (verdict == "paper").then_some(PaperFollowFillRecord {
        paper_fill_id,
        signal_id,
        wallet_event_id: event_id,
        entry_price,
        shares: copied_shares,
        notional,
        slippage_bps: args.slippage_bps,
        depth_snapshot_json,
        depth_status: depth_status.clone(),
        entry_at: emitted_at,
        exit_price: None,
        exit_at: None,
        pnl: None,
        pnl_bps: None,
        status: "open".to_string(),
    });
    let score = WalletFollowScoreRecord {
        account: fill.account.to_ascii_lowercase(),
        worth_following: if verdict == "paper" {
            "paper_watch".to_string()
        } else {
            "blocked".to_string()
        },
        latency_verdict: if latency_ms <= args.max_latency_secs * 1000 {
            "approved".to_string()
        } else {
            "rejected".to_string()
        },
        depth_verdict: if depth_status == "pass" {
            "approved".to_string()
        } else {
            "blocked".to_string()
        },
        edge_verdict: "blocked_pending_paper_exit".to_string(),
        overall_verdict: if verdict == "paper" {
            "paper_only".to_string()
        } else {
            "blocked".to_string()
        },
        score: score_for(verdict, latency_ms, args.max_latency_secs),
        metrics_json: json!({
            "fill_id": stored.id,
            "latency_ms": latency_ms,
            "copied_shares": copied_shares.to_string(),
            "copied_notional": notional.to_string(),
            "depth_status": depth_status,
            "reasons": reasons,
        })
        .to_string(),
    };

    Ok(FollowAction {
        event,
        signal,
        paper_fill,
        score,
    })
}

fn latest_depth_for_fill(
    storage: &Storage,
    stored: &StoredFill,
) -> Result<Option<FollowDepthSnapshot>> {
    if let Some(depth) = storage.latest_follow_depth_snapshot(&stored.fill.market_id)? {
        return Ok(Some(depth));
    }
    if let Some(outcome_id) = stored.fill.condition_id.as_deref() {
        return storage.latest_follow_depth_snapshot(outcome_id);
    }
    Ok(None)
}

fn depth_status(
    side: TradeSide,
    copied_shares: Decimal,
    min_depth_shares: Decimal,
    depth: Option<&FollowDepthSnapshot>,
) -> String {
    let Some(depth) = depth else {
        return "missing_depth".to_string();
    };
    let visible_depth = match side {
        TradeSide::Buy => depth.ask_depth,
        TradeSide::Sell => depth.bid_depth,
    };
    let Some(visible_depth) = visible_depth else {
        return "missing_side_depth".to_string();
    };
    let required = std::cmp::max(copied_shares, min_depth_shares);
    if visible_depth >= required {
        "pass".to_string()
    } else {
        "insufficient_depth".to_string()
    }
}

fn apply_slippage(price: Decimal, side: TradeSide, slippage_bps: Decimal) -> Decimal {
    let multiplier = slippage_bps / dec!(10000);
    match side {
        TradeSide::Buy => price * (Decimal::ONE + multiplier),
        TradeSide::Sell => price * (Decimal::ONE - multiplier),
    }
}

fn score_for(verdict: &str, latency_ms: i64, max_latency_secs: i64) -> Decimal {
    if verdict != "paper" {
        return Decimal::ZERO;
    }
    let max_latency_ms = max_latency_secs * 1000;
    if max_latency_ms <= 0 {
        return dec!(0.5);
    }
    let ratio = Decimal::from(latency_ms.min(max_latency_ms)) / Decimal::from(max_latency_ms);
    Decimal::ONE - ratio
}
