use std::time::Duration;

use anyhow::Result;
use oktrader_alpha::storage::Storage;
use serde_json::Value;

use crate::app::cli::AlertArgs;

const ALERT_CURSOR: &str = "alerts.last_fill_id";

pub async fn alerts(args: AlertArgs) -> Result<()> {
    let matched_only = !args.all_wallets;

    loop {
        let storage = Storage::open(&args.db)?;
        let mut cursor = alert_cursor(&storage)?;
        if cursor == 0 {
            cursor = storage.max_fill_id()?;
            storage.set_state(ALERT_CURSOR, &cursor.to_string())?;
            println!("alerts: initialized cursor at fill_id={cursor}");
        }

        let fills = storage.fills_after(cursor, args.limit, matched_only)?;
        for stored in &fills {
            print_alert(stored)?;
            cursor = stored.id;
        }
        if !fills.is_empty() {
            storage.set_state(ALERT_CURSOR, &cursor.to_string())?;
        } else {
            println!("alerts: no new fills");
        }

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(args.interval_secs)).await;
    }

    Ok(())
}

fn alert_cursor(storage: &Storage) -> Result<i64> {
    Ok(storage
        .get_state(ALERT_CURSOR)?
        .and_then(|value| value.parse().ok())
        .unwrap_or(0))
}

fn print_alert(stored: &oktrader_alpha::storage_alerts::StoredFill) -> Result<()> {
    let fill = &stored.fill;
    let profile = stored
        .matched_report_json
        .as_deref()
        .and_then(|json| serde_json::from_str::<Value>(json).ok())
        .and_then(|value| {
            value
                .get("strategy_profile")
                .or_else(|| value.get("primary_tag"))
                .and_then(Value::as_str)
                .map(ToOwned::to_owned)
        })
        .unwrap_or_else(|| "unmatched".to_string());
    let notional = fill.price * fill.shares;
    println!(
        "fill_alert id={} profile={} wallet={} side={} role={} market={} price={} shares={} notional={} tx={}",
        stored.id,
        profile,
        fill.account,
        fill.side,
        fill.role,
        fill.market_id,
        fill.price,
        fill.shares,
        notional,
        fill.tx_hash.as_deref().unwrap_or("-")
    );
    Ok(())
}
