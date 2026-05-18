import numpy as np
import polars as pl
from sklearn.neighbors import KernelDensity


def numeric(df: pl.DataFrame, column: str) -> np.ndarray:
    if column not in df.columns:
        return np.array([])
    return df.select(pl.col(column).drop_nulls()).to_series().to_numpy()


def quantile(values: np.ndarray, q: float) -> float:
    return float(np.quantile(values, q)) if len(values) else 0.0


def distribution(values: np.ndarray) -> dict:
    if len(values) == 0:
        return {"count": 0}
    return {
        "count": int(len(values)),
        "p10": quantile(values, 0.10),
        "p50": quantile(values, 0.50),
        "p90": quantile(values, 0.90),
        "kde_mode": kde_mode(values) if len(values) >= 5 else quantile(values, 0.50),
        "spike_zscore": spike_zscore(values),
    }


def kde_mode(values: np.ndarray) -> float:
    reshaped = values.reshape(-1, 1)
    bandwidth = max(float(np.std(values)), 1e-6)
    kde = KernelDensity(kernel="gaussian", bandwidth=bandwidth).fit(reshaped)
    grid = np.linspace(values.min(), values.max(), 200).reshape(-1, 1)
    return float(grid[np.argmax(kde.score_samples(grid))][0])


def spike_zscore(values: np.ndarray) -> float:
    if len(values) == 0:
        return 0.0
    std = float(np.std(values))
    if std == 0.0:
        return 0.0
    return float((np.max(values) - np.mean(values)) / std)
