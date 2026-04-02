from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch

from ml.asia_sweep_london_mss.model import AsiaSweepMLP
from ml.asia_sweep_london_mss.torch_dataset import FEATURE_COLS, StandardScalerStats, apply_standard_scaler


@dataclass
class LoadedArtifacts:
    model: AsiaSweepMLP
    scaler: StandardScalerStats
    symbol_map: Dict[str, int]
    metrics: Dict[str, Any]
    device: torch.device
    feature_cols: list[str]


_CACHE: Dict[tuple[str, str], LoadedArtifacts] = {}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_artifacts(model_dir: str | Path, *, device: Optional[str] = None) -> LoadedArtifacts:
    d = Path(model_dir)
    dev = (device or "").strip().lower()
    if not dev or dev == "auto":
        dev = "cuda" if torch.cuda.is_available() else "cpu"
    cache_key = (str(d.resolve()), dev)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    model_path = d / "model.pt"
    feat_path = d / "feature_stats.json"
    sym_path = d / "symbol_map.json"
    metrics_path = d / "metrics.json"

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not feat_path.exists():
        raise FileNotFoundError(feat_path)
    if not sym_path.exists():
        raise FileNotFoundError(sym_path)
    if not metrics_path.exists():
        raise FileNotFoundError(metrics_path)

    symbol_map = _load_json(sym_path)
    scaler = StandardScalerStats.from_json(_load_json(feat_path))
    metrics = _load_json(metrics_path)

    hidden = tuple(int(x) for x in metrics.get("hidden_sizes", [64, 32]))
    dropout = float(metrics.get("dropout", 0.1))
    emb_dim = int(metrics.get("symbol_emb_dim", 8))
    use_residual = bool(metrics.get("use_residual", False))

    # Use feature_cols from metrics if available (handles v1→v2 transition);
    # fall back to current FEATURE_COLS for new models.
    model_feature_cols = metrics.get("feature_cols", list(FEATURE_COLS))
    num_features = len(model_feature_cols)

    torch_device = torch.device(dev)
    model = AsiaSweepMLP(
        num_numeric_features=num_features,
        num_symbols=max(1, len(symbol_map)),
        symbol_emb_dim=emb_dim,
        hidden_sizes=hidden if hidden else (64, 32),
        dropout=dropout,
        use_residual=use_residual,
    ).to(torch_device)

    state = torch.load(str(model_path), map_location=torch_device)
    model.load_state_dict(state)
    model.eval()

    art = LoadedArtifacts(model=model, scaler=scaler, symbol_map=symbol_map, metrics=metrics, device=torch_device, feature_cols=model_feature_cols)
    _CACHE[cache_key] = art
    return art


def vectorize_features(features: Dict[str, Any], *, scaler: StandardScalerStats, feature_cols: Optional[list[str]] = None) -> np.ndarray:
    cols = feature_cols if feature_cols is not None else list(FEATURE_COLS)
    x = []
    for col in cols:
        v = features.get(col)
        try:
            vf = float(v)
        except Exception:
            vf = 0.0
        if not np.isfinite(vf):
            vf = 0.0
        x.append(vf)
    X = np.array([x], dtype=np.float32)
    X = apply_standard_scaler(X, scaler)
    return X


@torch.no_grad()
def score_probability(
    *,
    symbol: str,
    features: Dict[str, Any],
    model_dir: str | Path,
    device: Optional[str] = None,
) -> float:
    art = load_artifacts(model_dir, device=device)
    sym = str(symbol)
    if sym not in art.symbol_map:
        raise ValueError(f"Symbol not in symbol_map: {sym}")
    sym_id = int(art.symbol_map[sym])

    X = vectorize_features(features, scaler=art.scaler, feature_cols=art.feature_cols)
    xb = torch.tensor(X, dtype=torch.float32, device=art.device)
    sb = torch.tensor([sym_id], dtype=torch.long, device=art.device)
    logits = art.model(xb, sb)
    prob = torch.sigmoid(logits).detach().cpu().numpy().reshape(-1)[0]
    return float(prob)

