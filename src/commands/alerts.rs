use std::time::Duration;

use anyhow::{Context, Result};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_alerts::AlertMode;
use serde_json::Value;

use crate::app::cli::AlertArgs;

const ALERT_CURSOR: &str = "alerts.last_fill_id";

pub async fn alerts(args: AlertArgs) -> Result<()> {
    let mode = if args.all_wallets {
        AlertMode::All
    } else if args.watchlist {
        AlertMode::Watchlist
    } else {
        AlertMode::Matched
    };
    let http = reqwest::Client::new();

    loop {
        let storage = Storage::open(&args.db)?;
        let mut cursor = alert_cursor(&storage)?;
        if cursor == 0 {
            cursor = storage.max_fill_id()?;
            storage.set_state(ALERT_CURSOR, &cursor.to_string())?;
            println!("alerts: initialized cursor at fill_id={cursor}");
        }

        let fills = storage.fills_after(cursor, args.limit, mode)?;
        for stored in &fills {
            let message = alert_message(&storage, stored)?;
            println!("{message}");
            if let Some(url) = args.webhook_url.as_deref() {
                send_webhook(&http, url, &message).await?;
            }
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

fn alert_message(
    storage: &Storage,
    stored: &oktrader_alpha::storage_alerts::StoredFill,
) -> Result<String> {
    let fill = &stored.fill;
    let label = storage.watchlist_label(&fill.account)?;
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
        .or(label)
        .unwrap_or_else(|| "unmatched".to_string());
    let notional = fill.price * fill.shares;
    Ok(format!(
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
    ))
}

async fn send_webhook(http: &reqwest::Client, url: &str, text: &str) -> Result<()> {
    http.post(url)
        .json(&serde_json::json!({ "text": text }))
        .send()
        .await
        .context("failed to send webhook")?
        .error_for_status()
        .context("webhook returned error")?;
    Ok(())
}
