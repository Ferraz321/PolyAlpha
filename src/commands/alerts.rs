use std::{fs, time::Duration};

use anyhow::{Context, Result};
use chrono::Utc;
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_alerts::AlertMode;
use oktrader_alpha::storage_research::SignalRecord;
use oktrader_alpha::strategy_config::{
    StrategyConfig, matching_strategy_ids, parse_strategy_config,
};
use serde_json::{Value, json};

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
    let strategy_config = load_strategy_config(&args)?;

    loop {
        let storage = Storage::open(&args.db)?;
        if let Some(config) = strategy_config.as_ref() {
            crate::commands::strategy::upsert_strategies(&storage, config)?;
        }
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
            if let Some(trigger) =
                strategy_trigger_message(&storage, stored, strategy_config.as_ref())?
            {
                println!("{trigger}");
                if let Some(url) = args.webhook_url.as_deref() {
                    send_webhook(&http, url, &trigger).await?;
                }
            }
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

fn load_strategy_config(args: &AlertArgs) -> Result<Option<StrategyConfig>> {
    let Some(path) = args.strategy_config.as_ref() else {
        return Ok(None);
    };
    let content =
        fs::read_to_string(path).with_context(|| format!("failed to read {}", path.display()))?;
    Ok(Some(parse_strategy_config(&content)?))
}

fn alert_cursor(storage: &Storage) -> Result<i64> {
    Ok(storage
        .get_state(ALERT_CURSOR)?
        .and_then(|value| value.parse().ok())
        .unwrap_or(0))
}

fn strategy_trigger_message(
    storage: &Storage,
    stored: &oktrader_alpha::storage_alerts::StoredFill,
    config: Option<&StrategyConfig>,
) -> Result<Option<String>> {
    let Some(config) = config else {
        return Ok(None);
    };
    let fill = &stored.fill;
    let Some(snapshot) = storage.latest_feature_snapshot(&fill.market_id)? else {
        return Ok(None);
    };
    let matched = matching_strategy_ids(config, &snapshot);
    if matched.is_empty() {
        return Ok(None);
    }
    for strategy_id in &matched {
        let strategy_score = config
            .strategies
            .iter()
            .find(|strategy| &strategy.id == strategy_id)
            .map(|strategy| strategy.score)
            .unwrap_or(1.0);
        storage.insert_signal_record(&SignalRecord {
            signal_id: format!("strategy:{strategy_id}:fill:{}", stored.id),
            strategy_id: strategy_id.clone(),
            account: Some(fill.account.clone()),
            market_id: Some(fill.market_id.clone()),
            outcome_id: fill.condition_id.clone(),
            signal_type: "live_strategy_trigger".to_string(),
            score: strategy_score.to_string(),
            payload_json: json!({
                "fill_id": stored.id,
                "wallet": fill.account,
                "market": fill.market_id,
                "strategy_score": strategy_score,
                "ofi": snapshot.ofi,
                "spread": snapshot.spread,
                "depth_imbalance": snapshot.depth_imbalance,
                "price_momentum": snapshot.price_momentum,
            })
            .to_string(),
            emitted_at: Utc::now().to_rfc3339(),
            status: "new".to_string(),
        })?;
    }
    Ok(Some(format!(
        "strategy_trigger fill_id={} wallet={} market={} strategies={} ofi={:?} spread={:?} depth_imbalance={:?}",
        stored.id,
        fill.account,
        fill.market_id,
        matched.join(","),
        snapshot.ofi,
        snapshot.spread,
        snapshot.depth_imbalance,
    )))
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
