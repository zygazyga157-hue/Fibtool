from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
try:
    import torch
    from torch.utils.data import Dataset
except Exception:  # pragma: no cover
    torch = None  # type: ignore[assignment]
    Dataset = object  # type: ignore[misc,assignment]


# Keep feature list stable and explicit (plan-locked).
FEATURE_COLS: list[str] = [
    "asia_range",
    "atr14",
    "asia_range_atr",
    "eqh_touch_count",
    "eql_touch_count",
    "sweep_dir",
    "sweep_depth_atr",
    "minutes_from_london_open",
    "bars_from_sweep_to_mss",
    "bars_from_sweep_to_mss_norm",
    "confirm_range_atr",
    "entry_dist_atr",
    "rr",
    # --- v2 engineered features ---
    "day_of_week",
    "sweep_depth_x_asia_atr",
    "confirm_body_ratio",
    "rr_capped",
    "sweep_velocity_atr",
    "multi_touch",
    "entry_stop_atr",
]


@dataclass
class StandardScalerStats:
    mean: np.ndarray  # shape: (features,)
    std: np.ndarray  # shape: (features,)

    def to_json(self) -> dict:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_json(cls, obj: dict) -> "StandardScalerStats":
        return cls(mean=np.array(obj["mean"], dtype=np.float32), std=np.array(obj["std"], dtype=np.float32))


def load_dataset_csv(csv_path: str | Path) -> pd.DataFrame:
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_csv(p)
    if "t0" not in df.columns or "symbol" not in df.columns or "label" not in df.columns:
        raise ValueError("dataset CSV must include columns: t0, symbol, label")
    df["t0"] = pd.to_datetime(df["t0"], errors="coerce", utc=True)
    df = df.dropna(subset=["t0"]).sort_values("t0").reset_index(drop=True)
    return df


def build_symbol_map(symbols: Iterable[str]) -> Dict[str, int]:
    uniq = sorted({str(s) for s in symbols if str(s).strip()})
    return {s: i for i, s in enumerate(uniq)}


def time_based_split(
    df: pd.DataFrame,
    *,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split by sorted t0 (no random shuffling, prevents leakage)."""
    if not (0.0 < val_frac < 1.0) or not (0.0 < test_frac < 1.0) or (val_frac + test_frac) >= 1.0:
        raise ValueError("val_frac and test_frac must be in (0,1) and sum to < 1")
    df = df.sort_values("t0").reset_index(drop=True)
    n = len(df)
    if n < 10:
        # tiny dataset: keep everything in train
        return df, df.iloc[:0].copy(), df.iloc[:0].copy()

    n_test = max(1, int(round(n * float(test_frac))))
    n_val = max(1, int(round(n * float(val_frac))))
    n_train = max(1, n - n_val - n_test)
    if n_train < 1:
        n_train = max(1, n - n_test)
        n_val = n - n_train - n_test
        n_val = max(0, n_val)

    train = df.iloc[:n_train].copy()
    val = df.iloc[n_train : n_train + n_val].copy()
    test = df.iloc[n_train + n_val :].copy()
    return train, val, test


def fit_standard_scaler(X: np.ndarray) -> StandardScalerStats:
    mean = np.nanmean(X, axis=0).astype(np.float32)
    std = (np.nanstd(X, axis=0) + 1e-9).astype(np.float32)
    return StandardScalerStats(mean=mean, std=std)


def apply_standard_scaler(X: np.ndarray, stats: StandardScalerStats) -> np.ndarray:
    out = (X - stats.mean) / stats.std
    # replace NaNs/infs after scaling (safe default)
    out = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    return out


def save_json(path: str | Path, obj: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def smote_oversample(
    df: pd.DataFrame,
    feature_cols: list[str],
    *,
    target_ratio: float = 0.35,
    k_neighbors: int = 5,
    seed: int = 1337,
) -> pd.DataFrame:
    """SMOTE oversampling of minority class (label=1) in feature space.

    Generates synthetic positive samples by interpolating between existing
    positives and their k-nearest neighbors. Only augments the training set.

    Args:
        df: DataFrame with 'label' column and feature_cols.
        target_ratio: Desired fraction of positives after oversampling (default 0.35 = ~1:2 ratio).
        k_neighbors: Number of neighbors for SMOTE interpolation.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with original rows + synthetic positive rows appended.
    """
    rng = np.random.RandomState(seed)
    pos = df[df["label"] == 1].copy()
    neg = df[df["label"] == 0].copy()
    n_pos = len(pos)
    n_neg = len(neg)

    if n_pos == 0 or n_neg == 0:
        return df

    # How many synthetic positives to generate
    desired_pos = int(round((n_neg * target_ratio) / (1.0 - target_ratio)))
    n_synthetic = max(0, desired_pos - n_pos)
    if n_synthetic == 0:
        return df

    X_pos = pos[feature_cols].astype(np.float32).values
    X_pos = np.nan_to_num(X_pos, nan=0.0, posinf=0.0, neginf=0.0)

    # Limit k to available neighbors
    k = min(k_neighbors, n_pos - 1)
    if k < 1:
        # Not enough neighbors for SMOTE — duplicate with noise instead
        synthetic_rows = []
        for _ in range(n_synthetic):
            idx = rng.randint(0, n_pos)
            row = pos.iloc[idx].copy()
            # Add small gaussian noise to numeric features
            for col in feature_cols:
                val = float(row[col]) if np.isfinite(float(row[col])) else 0.0
                noise = rng.normal(0, max(abs(val) * 0.05, 1e-6))
                row[col] = val + noise
            synthetic_rows.append(row)
        synthetic_df = pd.DataFrame(synthetic_rows)
        return pd.concat([df, synthetic_df], ignore_index=True)

    # Compute pairwise distances for KNN
    from numpy.linalg import norm
    dists = np.zeros((n_pos, n_pos), dtype=np.float32)
    for i in range(n_pos):
        for j in range(i + 1, n_pos):
            d = norm(X_pos[i] - X_pos[j])
            dists[i, j] = d
            dists[j, i] = d
        dists[i, i] = np.inf  # exclude self

    # Find k nearest neighbors for each positive
    nn_indices = np.argsort(dists, axis=1)[:, :k]

    synthetic_rows = []
    for _ in range(n_synthetic):
        idx = rng.randint(0, n_pos)
        nn_idx = nn_indices[idx, rng.randint(0, k)]
        lam = rng.uniform(0.0, 1.0)
        synth_x = X_pos[idx] + lam * (X_pos[nn_idx] - X_pos[idx])

        row = pos.iloc[idx].copy()
        for ci, col in enumerate(feature_cols):
            row[col] = float(synth_x[ci])
        # Keep the original symbol and label
        row["label"] = 1
        synthetic_rows.append(row)

    synthetic_df = pd.DataFrame(synthetic_rows)
    result = pd.concat([df, synthetic_df], ignore_index=True)
    return result


class AsiaSweepTabularDataset(Dataset):
    """Torch Dataset returning (x_num, symbol_id, y)."""

    def __init__(
        self,
        df: pd.DataFrame,
        *,
        feature_cols: Sequence[str] = FEATURE_COLS,
        symbol_map: Dict[str, int],
        scaler: Optional[StandardScalerStats] = None,
    ):
        if torch is None:
            raise RuntimeError("torch is required to use AsiaSweepTabularDataset (install torch).")

        self.df = df.reset_index(drop=True)
        self.feature_cols = list(feature_cols)
        self.symbol_map = dict(symbol_map)

        X = self.df[self.feature_cols].astype(np.float32).values
        if scaler is not None:
            X = apply_standard_scaler(X, scaler)
        else:
            X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

        sym = [self.symbol_map.get(str(s), 0) for s in self.df["symbol"].astype(str).tolist()]
        y = self.df["label"].fillna(0).astype(int).values

        self.X = torch.from_numpy(X)
        self.sym = torch.tensor(sym, dtype=torch.long)
        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.y.shape[0])

    def __getitem__(self, idx: int):
        return self.X[idx], self.sym[idx], self.y[idx]
