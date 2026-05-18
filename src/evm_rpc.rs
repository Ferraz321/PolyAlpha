use anyhow::{Context, Result, bail};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

#[derive(Clone)]
pub struct EvmRpc {
    url: String,
    http: Client,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EvmLog {
    #[allow(dead_code)]
    pub address: String,
    pub topics: Vec<String>,
    pub data: String,
    #[serde(rename = "blockNumber")]
    pub block_number: String,
    #[serde(rename = "transactionHash")]
    pub transaction_hash: String,
    #[serde(rename = "logIndex")]
    #[allow(dead_code)]
    pub log_index: String,
}

#[derive(Debug, Clone, Serialize)]
struct LogFilter<'a> {
    address: &'a str,
    #[serde(rename = "fromBlock")]
    from_block: String,
    #[serde(rename = "toBlock")]
    to_block: String,
    topics: Vec<String>,
}

impl EvmRpc {
    pub fn new(url: String) -> Self {
        Self {
            url,
            http: Client::new(),
        }
    }

    pub async fn block_number(&self) -> Result<u64> {
        let value = self.call("eth_blockNumber", json!([])).await?;
        hex_u64(value.as_str().context("block number must be hex string")?)
    }

    pub async fn block_timestamp(&self, block: u64) -> Result<i64> {
        let value = self
            .call("eth_getBlockByNumber", json!([hex_quantity(block), false]))
            .await?;
        let timestamp = value
            .get("timestamp")
            .and_then(Value::as_str)
            .context("block timestamp missing")?;
        Ok(hex_u64(timestamp)? as i64)
    }

    pub async fn logs(
        &self,
        address: &str,
        topic0: &str,
        from_block: u64,
        to_block: u64,
    ) -> Result<Vec<EvmLog>> {
        let filter = LogFilter {
            address,
            from_block: hex_quantity(from_block),
            to_block: hex_quantity(to_block),
            topics: vec![topic0.to_string()],
        };
        let value = self.call("eth_getLogs", json!([filter])).await?;
        serde_json::from_value(value).context("failed to decode eth_getLogs response")
    }

    async fn call(&self, method: &str, params: Value) -> Result<Value> {
        let response = self
            .http
            .post(&self.url)
            .json(&json!({
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params,
            }))
            .send()
            .await
            .context("rpc request failed")?
            .error_for_status()
            .context("rpc returned http error")?
            .json::<Value>()
            .await
            .context("rpc returned invalid json")?;

        if let Some(error) = response.get("error") {
            bail!("rpc error for {method}: {error}");
        }
        response
            .get("result")
            .cloned()
            .context("rpc response missing result")
    }
}

pub fn hex_u64(value: &str) -> Result<u64> {
    Ok(u64::from_str_radix(value.trim_start_matches("0x"), 16)?)
}

pub fn hex_quantity(value: u64) -> String {
    format!("0x{value:x}")
}
