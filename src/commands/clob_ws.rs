use std::fs;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use chrono::Utc;
use futures_util::{SinkExt, StreamExt};
use oktrader_alpha::storage::Storage;
use oktrader_alpha::storage_types::RawClobEventRecord;
use serde_json::{Value, json};
use tiny_keccak::{Hasher, Keccak};
use tokio_tungstenite::{connect_async, tungstenite::Message};

use crate::app::cli::WatchClobArgs;

pub async fn watch_clob(args: WatchClobArgs) -> Result<()> {
    if args.chunk_size == 0 {
        bail!("--chunk-size must be greater than zero");
    }
    if args.reconnect_min_secs == 0 || args.reconnect_max_secs < args.reconnect_min_secs {
        bail!("reconnect max must be >= reconnect min, and both must be positive");
    }

    let storage = Storage::open(&args.db)?;
    storage.init()?;
    let assets = load_assets(&args.assets_file)?;
    let mut backoff_secs = args.reconnect_min_secs;

    loop {
        match run_connection(&args, &storage, &assets).await {
            Ok(ClobRun::Finished) => break,
            Ok(ClobRun::Disconnected) => {
                println!("watch-clob: disconnected, reconnecting in {backoff_secs}s");
            }
            Err(error) => {
                tracing::warn!(%error, "watch-clob connection failed");
                println!("watch-clob: error, reconnecting in {backoff_secs}s");
            }
        }

        if args.once {
            break;
        }
        tokio::time::sleep(Duration::from_secs(backoff_secs)).await;
        backoff_secs = (backoff_secs * 2).min(args.reconnect_max_secs);
    }

    Ok(())
}

enum ClobRun {
    Finished,
    Disconnected,
}

async fn run_connection(
    args: &WatchClobArgs,
    storage: &Storage,
    assets: &[String],
) -> Result<ClobRun> {
    let (mut socket, _) = connect_async(&args.ws_url)
        .await
        .with_context(|| format!("failed to connect {}", args.ws_url))?;
    subscribe_assets(&mut socket, assets, args.chunk_size).await?;

    let mut ping = tokio::time::interval(Duration::from_secs(args.ping_secs));
    let mut inserted = 0usize;
    loop {
        tokio::select! {
            _ = ping.tick() => {
                socket.send(Message::Text("PING".into())).await?;
            }
            message = socket.next() => {
                let Some(message) = message else { break };
                let message = message?;
                if let Some(payload) = payload_text(message)? {
                    for record in records_from_payload(&payload)? {
                        if storage.insert_raw_clob_event(&record)? {
                            inserted += 1;
                        }
                    }
                    println!("watch-clob: inserted_raw_events={inserted}");
                    if args.once {
                        return Ok(ClobRun::Finished);
                    }
                }
            }
        }
    }

    Ok(ClobRun::Disconnected)
}

async fn subscribe_assets(
    socket: &mut tokio_tungstenite::WebSocketStream<
        tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>,
    >,
    assets: &[String],
    chunk_size: usize,
) -> Result<()> {
    for chunk in assets.chunks(chunk_size) {
        let message = json!({
            "assets_ids": chunk,
            "type": "market",
            "custom_feature_enabled": true
        });
        socket
            .send(Message::Text(message.to_string().into()))
            .await?;
    }
    Ok(())
}

fn load_assets(path: &std::path::Path) -> Result<Vec<String>> {
    let content = fs::read_to_string(path)
        .with_context(|| format!("failed to read assets file {}", path.display()))?;
    let assets = content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(ToOwned::to_owned)
        .collect::<Vec<_>>();
    if assets.is_empty() {
        bail!("assets file is empty");
    }
    Ok(assets)
}

fn payload_text(message: Message) -> Result<Option<String>> {
    match message {
        Message::Text(text) => {
            let text = text.to_string();
            Ok((text != "PONG").then_some(text))
        }
        Message::Binary(bytes) => Ok(Some(String::from_utf8(bytes.to_vec())?)),
        Message::Ping(_) | Message::Pong(_) => Ok(None),
        Message::Close(_) => Ok(None),
        Message::Frame(_) => Ok(None),
    }
}

fn records_from_payload(payload: &str) -> Result<Vec<RawClobEventRecord>> {
    let value: Value =
        serde_json::from_str(payload).unwrap_or_else(|_| Value::String(payload.into()));
    let received_at = Utc::now().to_rfc3339();
    match value {
        Value::Array(items) => items
            .into_iter()
            .enumerate()
            .map(|(index, item)| record_from_value(item, &received_at, index))
            .collect(),
        item => Ok(vec![record_from_value(item, &received_at, 0)?]),
    }
}

fn record_from_value(value: Value, received_at: &str, index: usize) -> Result<RawClobEventRecord> {
    let event_type = string_field(&value, &["event_type", "type"]);
    let asset_id = string_field(&value, &["asset_id", "asset", "token_id"]);
    let payload = match value {
        Value::String(text) => text,
        other => serde_json::to_string(&other)?,
    };
    Ok(RawClobEventRecord {
        channel: "market".to_string(),
        event_type,
        asset_id,
        stable_key: stable_key(&payload, received_at, index),
        payload,
        received_at: received_at.to_string(),
    })
}

fn string_field(value: &Value, keys: &[&str]) -> Option<String> {
    keys.iter()
        .find_map(|key| value.get(key).and_then(Value::as_str))
        .map(ToOwned::to_owned)
}

fn stable_key(payload: &str, received_at: &str, index: usize) -> String {
    let mut hasher = Keccak::v256();
    let mut out = [0u8; 32];
    hasher.update(payload.as_bytes());
    hasher.update(received_at.as_bytes());
    hasher.update(index.to_string().as_bytes());
    hasher.finalize(&mut out);
    format!("clob:{}", hex_encode(&out))
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}
