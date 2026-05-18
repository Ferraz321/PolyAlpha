import numpy as np
import polars as pl
from sklearn.ensemble import RandomForestClassifier

from .factor_library import available_specs
from .statistics import numeric


def run_research_matrix(factors: pl.DataFrame, engines: list[str]) -> dict:
    enabled = set(engines)
    out = {"enabled": engines, "engines": {}}
    if "core" in enabled:
        out["engines"]["core"] = _core_summary(factors)
    if "alphalens" in enabled:
        out["engines"]["alphalens"] = _alphalens_like(factors)
    if "shap" in enabled:
        out["engines"]["shap"] = _shap_like(factors)
    if "stumpy" in enabled:
        out["engines"]["stumpy"] = _stumpy_like(factors)
    if "nautilus" in enabled:
        out["engines"]["nautilus"] = _nautilus_manifest()
    if "agent" in enabled:
        out["engines"]["agent"] = _agent_brief(out["engines"])
    return out


def _core_summary(factors: pl.DataFrame) -> dict:
    specs = available_specs(factors)
    return {
        "status": "ok",
        "rows": factors.height,
        "factor_columns": [spec.column for spec in specs],
        "wallets": factors.get_column("account").n_unique() if "account" in factors.columns else 0,
        "markets": factors.get_column("market_id").n_unique() if "market_id" in factors.columns else 0,
    }


def _alphalens_like(factors: pl.DataFrame) -> dict:
    df = _with_forward_move(factors)
    if "forward_price_move" not in df.columns:
        return {"status": "insufficient_data", "reason": "missing price column"}
    rows = []
    for spec in available_specs(df):
        x = numeric(df, spec.column)
        y = numeric(df, "forward_price_move")
        n = min(len(x), len(y))
        if n < 5 or np.std(x[:n]) == 0.0 or np.std(y[:n]) == 0.0:
            continue
        rows.append(
            {
                "factor": spec.column,
                "ic": float(np.corrcoef(x[:n], y[:n])[0, 1]),
                "coverage": n / df.height if df.height else 0.0,
            }
        )
    rows.sort(key=lambda row: abs(row["ic"]), reverse=True)
    return {"status": "ok", "top_ic": rows[:10]}


def _shap_like(factors: pl.DataFrame) -> dict:
    feature_cols = [spec.column for spec in available_specs(factors)]
    if len(feature_cols) < 2 or "side" not in factors.columns:
        return {"status": "insufficient_data", "reason": "need side labels and 2+ factors"}
    model_df = factors.select(feature_cols + ["side"]).drop_nulls()
    if model_df.height < 20:
        return {"status": "insufficient_data", "reason": "need at least 20 labeled rows"}
    x = model_df.select(feature_cols).to_numpy()
    y = (model_df.get_column("side").str.to_lowercase() == "buy").cast(pl.Int8).to_numpy()
    model = RandomForestClassifier(n_estimators=64, max_depth=4, random_state=7)
    model.fit(x, y)
    importances = [
        {"factor": name, "importance": float(value)}
        for name, value in zip(feature_cols, model.feature_importances_)
    ]
    importances.sort(key=lambda row: row["importance"], reverse=True)
    return {"status": "ok", "method": "random_forest_importance", "top_features": importances[:10]}


def _stumpy_like(factors: pl.DataFrame) -> dict:
    if "ofi_filled" not in factors.columns:
        return {"status": "insufficient_data", "reason": "missing ofi_filled"}
    series = numeric(factors.sort("timestamp"), "ofi_filled")
    if len(series) < 12:
        return {"status": "insufficient_data", "reason": "need at least 12 observations"}
    window = min(8, max(3, len(series) // 4))
    motifs = []
    for start in range(0, len(series) - window + 1):
        segment = series[start : start + window]
        z = _z_norm(segment)
        distance = float(np.linalg.norm(z - _z_norm(series[-window:])))
        motifs.append({"start": start, "window": window, "distance_to_recent": distance})
    motifs.sort(key=lambda row: row["distance_to_recent"])
    return {"status": "ok", "method": "matrix_profile_light", "motifs": motifs[:5]}


def _nautilus_manifest() -> dict:
    return {
        "status": "adapter_ready",
        "role": "event-driven replay target for strategy_config.json",
        "required_inputs": ["LOB event stream", "fills", "strategy_config.json"],
    }


def _agent_brief(engines: dict) -> dict:
    suggestions = ["run profile-readiness before accepting any strategy claim"]
    if engines.get("alphalens", {}).get("status") != "ok":
        suggestions.append("collect more CLOB-aligned rows to compute IC evidence")
    if engines.get("shap", {}).get("status") == "ok":
        suggestions.append("review top model features before enabling live strategy rules")
    if engines.get("stumpy", {}).get("status") != "ok":
        suggestions.append("collect longer pre-trade sequences for motif mining")
    return {"status": "ok", "suggestions": suggestions}


def _with_forward_move(factors: pl.DataFrame) -> pl.DataFrame:
    if "price" not in factors.columns or "market_id" not in factors.columns:
        return factors
    return factors.sort(["market_id", "timestamp"]).with_columns(
        (pl.col("price").shift(-1).over("market_id") - pl.col("price")).alias("forward_price_move")
    )


def _z_norm(values: np.ndarray) -> np.ndarray:
    std = np.std(values)
    if std == 0.0:
        return values * 0.0
    return (values - np.mean(values)) / std
