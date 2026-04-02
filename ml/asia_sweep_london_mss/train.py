from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

import math
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


class FocalLossWithLogits(nn.Module):
    """Focal loss for binary classification with class imbalance.

    Reduces contribution of well-classified examples, focusing training
    on hard-to-classify cases. Particularly effective for severe imbalance
    (10.88% positive rate in our dataset).

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)
    """

    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, pos_weight: Optional[torch.Tensor] = None):
        super().__init__()
        self.alpha = float(alpha)
        self.gamma = float(gamma)
        self.pos_weight = pos_weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        p = torch.sigmoid(logits)
        ce = nn.functional.binary_cross_entropy_with_logits(
            logits, targets, reduction="none",
            pos_weight=self.pos_weight,
        )
        p_t = p * targets + (1 - p) * (1 - targets)
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        focal_weight = alpha_t * (1 - p_t).pow(self.gamma)
        return (focal_weight * ce).mean()


def _ensure_project_root_on_path() -> None:
    # __file__ = <repo>/ml/asia_sweep_london_mss/train.py  -> repo root is parents[3]
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_project_root_on_path()

from ml.asia_sweep_london_mss.model import AsiaSweepMLP  # noqa: E402
from ml.asia_sweep_london_mss.torch_dataset import (  # noqa: E402
    FEATURE_COLS,
    AsiaSweepTabularDataset,
    StandardScalerStats,
    apply_standard_scaler,
    build_symbol_map,
    fit_standard_scaler,
    load_dataset_csv,
    save_json,
    smote_oversample,
    time_based_split,
)


def set_seeds(seed: int = 1337) -> None:
    np.random.seed(int(seed))
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))


def roc_auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """ROC AUC with tie-handling (rank-based Mann–Whitney U). No sklearn dependency."""
    y_true = np.asarray(y_true).astype(int)
    y_score = np.asarray(y_score).astype(float)
    mask = np.isfinite(y_score)
    y_true = y_true[mask]
    y_score = y_score[mask]
    n = len(y_true)
    if n == 0:
        return float("nan")
    n_pos = int((y_true == 1).sum())
    n_neg = int((y_true == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    order = np.argsort(y_score)
    scores_sorted = y_score[order]
    y_sorted = y_true[order]

    ranks = np.empty(n, dtype=float)
    i = 0
    # ranks are 1..n
    while i < n:
        j = i
        while j + 1 < n and scores_sorted[j + 1] == scores_sorted[i]:
            j += 1
        # average rank for ties in [i..j]
        avg_rank = (i + j + 2) / 2.0
        ranks[i : j + 1] = avg_rank
        i = j + 1

    rank_sum_pos = float(ranks[y_sorted == 1].sum())
    auc = (rank_sum_pos - (n_pos * (n_pos + 1) / 2.0)) / float(n_pos * n_neg)
    return float(auc)


@torch.no_grad()
def evaluate(model: AsiaSweepMLP, loader: DataLoader, device: torch.device) -> Tuple[float, float]:
    model.eval()
    ys = []
    ps = []
    for xb, sym, yb in loader:
        xb = xb.to(device)
        sym = sym.to(device)
        logits = model(xb, sym)
        prob = torch.sigmoid(logits).detach().cpu().numpy()
        ps.append(prob)
        ys.append(yb.detach().cpu().numpy())
    y = np.concatenate(ys) if ys else np.array([])
    p = np.concatenate(ps) if ps else np.array([])
    auc = roc_auc_score(y, p) if len(y) else float("nan")
    acc = float(((p > 0.5).astype(int) == y.astype(int)).mean()) if len(y) else float("nan")
    return auc, acc


@torch.no_grad()
def evaluate_rich(model: AsiaSweepMLP, loader: DataLoader, device: torch.device, threshold: float = 0.5) -> dict:
    """Return AUC, accuracy, precision, recall, F1, confusion matrix."""
    model.eval()
    ys = []
    ps = []
    for xb, sym, yb in loader:
        xb = xb.to(device)
        sym = sym.to(device)
        logits = model(xb, sym)
        prob = torch.sigmoid(logits).detach().cpu().numpy()
        ps.append(prob)
        ys.append(yb.detach().cpu().numpy())
    y = np.concatenate(ys) if ys else np.array([])
    p = np.concatenate(ps) if ps else np.array([])
    if len(y) == 0:
        return {"auc": float("nan"), "acc": float("nan"), "precision": float("nan"),
                "recall": float("nan"), "f1": float("nan"), "confusion": [[0, 0], [0, 0]]}

    pred = (p > threshold).astype(int)
    y_int = y.astype(int)

    tp = int(((pred == 1) & (y_int == 1)).sum())
    fp = int(((pred == 1) & (y_int == 0)).sum())
    fn = int(((pred == 0) & (y_int == 1)).sum())
    tn = int(((pred == 0) & (y_int == 0)).sum())

    auc = roc_auc_score(y, p)
    acc = float((pred == y_int).mean())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    return {
        "auc": auc, "acc": acc, "precision": precision, "recall": recall, "f1": f1,
        "confusion": [[tn, fp], [fn, tp]],  # [[TN, FP], [FN, TP]]
        "threshold": threshold,
    }


def train_epoch(
    model: AsiaSweepMLP,
    loader: DataLoader,
    optim: torch.optim.Optimizer,
    loss_fn: nn.Module,
    device: torch.device,
) -> float:
    model.train()
    total = 0
    total_loss = 0.0
    for xb, sym, yb in loader:
        xb = xb.to(device)
        sym = sym.to(device)
        yb = yb.to(device)
        optim.zero_grad()
        logits = model(xb, sym)
        loss = loss_fn(logits, yb)
        loss.backward()
        optim.step()
        total_loss += float(loss.item()) * int(xb.shape[0])
        total += int(xb.shape[0])
    return float(total_loss / max(1, total))


def time_series_cv_folds(df: pd.DataFrame, n_folds: int) -> list[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Generate expanding-window time-series CV folds.

    Each fold uses an expanding training window and a fixed-size val window.
    Fold 1: train on [0..split1), val on [split1..split2)
    Fold 2: train on [0..split2), val on [split2..split3)
    etc.
    """
    df = df.sort_values("t0").reset_index(drop=True)
    n = len(df)
    fold_size = n // (n_folds + 1)
    if fold_size < 5:
        raise ValueError(f"Dataset too small ({n} rows) for {n_folds}-fold CV")
    folds = []
    for i in range(n_folds):
        train_end = fold_size * (i + 1)
        val_end = min(fold_size * (i + 2), n)
        folds.append((df.iloc[:train_end].copy(), df.iloc[train_end:val_end].copy()))
    return folds


def run_cv(args, df: "pd.DataFrame", device: torch.device) -> dict:
    """Run time-series cross-validation and return pooled metrics."""
    folds = time_series_cv_folds(df, n_folds=int(args.cv_folds))
    symbol_map = build_symbol_map(df["symbol"].tolist())
    hidden_sizes = tuple(int(x.strip()) for x in str(args.hidden).split(",") if x.strip())

    all_y = []
    all_p = []
    fold_aucs = []

    for fold_idx, (train_df, val_df) in enumerate(folds):
        set_seeds(int(args.seed) + fold_idx)

        if args.smote:
            n_pos_before = int((train_df["label"] == 1).sum())
            train_df = smote_oversample(train_df, list(FEATURE_COLS), target_ratio=float(args.smote_ratio))
            n_pos_after = int((train_df["label"] == 1).sum())
            if fold_idx == 0:
                print(f"    SMOTE: {n_pos_before} -> {n_pos_after} positives (total {len(train_df)})")

        X_train = train_df[FEATURE_COLS].astype(np.float32).values
        scaler = fit_standard_scaler(X_train)

        train_ds = AsiaSweepTabularDataset(train_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler)
        val_ds = AsiaSweepTabularDataset(val_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler)

        train_loader = DataLoader(train_ds, batch_size=int(args.batch), shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=int(args.batch), shuffle=False)

        model = AsiaSweepMLP(
            num_numeric_features=len(FEATURE_COLS),
            num_symbols=max(1, len(symbol_map)),
            symbol_emb_dim=int(args.symbol_emb_dim),
            hidden_sizes=hidden_sizes if hidden_sizes else (64, 32),
            dropout=float(args.dropout),
            use_residual=bool(args.residual),
        ).to(device)

        y_train = train_df["label"].fillna(0).astype(int).values
        pos = int((y_train == 1).sum())
        neg = int((y_train == 0).sum())
        pw = torch.tensor([neg / max(1, pos)], dtype=torch.float32, device=device) if pos > 0 else torch.tensor([1.0], dtype=torch.float32, device=device)

        if args.focal_loss:
            loss_fn = FocalLossWithLogits(alpha=float(args.focal_alpha), gamma=float(args.focal_gamma), pos_weight=pw)
        else:
            loss_fn = nn.BCEWithLogitsLoss(pos_weight=pw)

        optim = torch.optim.Adam(model.parameters(), lr=float(args.lr))

        best_val_auc = None
        patience_left = int(args.patience)
        best_state = None

        for epoch in range(1, int(args.epochs) + 1):
            train_epoch(model, train_loader, optim, loss_fn, device)
            val_auc, _ = evaluate(model, val_loader, device)

            improved = best_val_auc is None or (val_auc == val_auc and val_auc > best_val_auc)
            if improved:
                best_val_auc = val_auc
                patience_left = int(args.patience)
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                patience_left -= 1
                if patience_left <= 0:
                    break

        if best_state is not None:
            model.load_state_dict(best_state)

        # Collect predictions on this fold's val set
        model.eval()
        ys, ps = [], []
        with torch.no_grad():
            for xb, sym, yb in val_loader:
                xb, sym = xb.to(device), sym.to(device)
                prob = torch.sigmoid(model(xb, sym)).detach().cpu().numpy()
                ps.append(prob)
                ys.append(yb.numpy())

        y_fold = np.concatenate(ys)
        p_fold = np.concatenate(ps)
        all_y.append(y_fold)
        all_p.append(p_fold)

        fold_auc = roc_auc_score(y_fold, p_fold) if len(y_fold) and int((y_fold == 1).sum()) > 0 else float("nan")
        fold_aucs.append(fold_auc)
        n_pos = int((y_fold == 1).sum())
        print(f"  fold {fold_idx + 1}/{len(folds)}: n_train={len(train_df)}, n_val={len(val_df)}, pos={n_pos}, val_auc={fold_auc:.4f}")

    # Pool all fold predictions
    y_all = np.concatenate(all_y)
    p_all = np.concatenate(all_p)
    pooled_auc = roc_auc_score(y_all, p_all) if len(y_all) and int((y_all == 1).sum()) > 0 else float("nan")

    pred = (p_all > 0.5).astype(int)
    y_int = y_all.astype(int)
    tp = int(((pred == 1) & (y_int == 1)).sum())
    fp = int(((pred == 1) & (y_int == 0)).sum())
    fn = int(((pred == 0) & (y_int == 1)).sum())
    tn = int(((pred == 0) & (y_int == 0)).sum())
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)

    valid_aucs = [a for a in fold_aucs if math.isfinite(a)]
    mean_auc = float(np.mean(valid_aucs)) if valid_aucs else float("nan")
    std_auc = float(np.std(valid_aucs)) if valid_aucs else float("nan")

    print(f"\n  CV pooled: auc={pooled_auc:.4f}  mean_fold_auc={mean_auc:.4f} +/- {std_auc:.4f}")
    print(f"  precision={precision:.4f}  recall={recall:.4f}  f1={f1:.4f}")
    print(f"  confusion: [[TN={tn}, FP={fp}], [FN={fn}, TP={tp}]]")
    print(f"  total samples pooled: {len(y_all)} (pos={int((y_int == 1).sum())})")

    return {
        "cv_folds": int(args.cv_folds),
        "fold_aucs": [float(a) if math.isfinite(a) else None for a in fold_aucs],
        "pooled_auc": float(pooled_auc) if math.isfinite(pooled_auc) else None,
        "mean_fold_auc": float(mean_auc) if math.isfinite(mean_auc) else None,
        "std_fold_auc": float(std_auc) if math.isfinite(std_auc) else None,
        "pooled_precision": precision,
        "pooled_recall": recall,
        "pooled_f1": f1,
        "pooled_confusion": [[tn, fp], [fn, tp]],
        "total_pooled": len(y_all),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Dataset CSV produced by prepare_dataset.py")
    ap.add_argument("--out", default="outputs/models/asia_sweep_mss/v1", help="Output dir for artifacts")
    ap.add_argument(
        "--activate-root",
        default="",
        help="Optional model root to update current.json pointer after training (e.g. outputs/models/asia_sweep_mss)",
    )
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--batch", type=int, default=256)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--hidden", default="64,32")
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--symbol-emb-dim", type=int, default=8)
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--device", default="", help="cpu|cuda|auto (default auto)")
    ap.add_argument("--focal-loss", action="store_true", help="Use focal loss instead of BCE (better for imbalance)")
    ap.add_argument("--focal-alpha", type=float, default=0.25, help="Focal loss alpha (default 0.25)")
    ap.add_argument("--focal-gamma", type=float, default=2.0, help="Focal loss gamma (default 2.0)")
    ap.add_argument("--cv-folds", type=int, default=0, help="Stratified time-series CV folds (0=disabled, use single split)")
    ap.add_argument("--residual", action="store_true", help="Enable residual connections in MLP blocks")
    ap.add_argument("--smote", action="store_true", help="Apply SMOTE oversampling to training minority class")
    ap.add_argument("--smote-ratio", type=float, default=0.35, help="Target positive class ratio after SMOTE (default 0.35)")
    args = ap.parse_args()

    set_seeds(int(args.seed))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset_csv(args.data)

    # Resolve device early (needed for both CV and standard paths)
    device = None
    if str(args.device).strip().lower() == "cpu":
        device = torch.device("cpu")
    elif str(args.device).strip().lower() == "cuda":
        device = torch.device("cuda")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # If --cv-folds > 0, run time-series CV for reliable evaluation, then exit.
    if int(args.cv_folds) > 0:
        print(f"Running {args.cv_folds}-fold time-series cross-validation...")
        cv_results = run_cv(args, df, device)
        save_json(out_dir / "cv_metrics.json", cv_results)
        print(f"\nSaved CV metrics: {out_dir / 'cv_metrics.json'}")
        return

    # plan: global multi-symbol model with symbol embedding
    symbol_map = build_symbol_map(df["symbol"].tolist())
    save_json(out_dir / "symbol_map.json", symbol_map)

    # Split by time (no leakage)
    train_df, val_df, test_df = time_based_split(df, val_frac=float(args.val_frac), test_frac=float(args.test_frac))

    # Apply SMOTE to training data only (before scaling)
    if args.smote:
        n_pos_before = int((train_df["label"] == 1).sum())
        train_df = smote_oversample(train_df, list(FEATURE_COLS), target_ratio=float(args.smote_ratio))
        n_pos_after = int((train_df["label"] == 1).sum())
        print(f"SMOTE: {n_pos_before} -> {n_pos_after} positives in train (total {len(train_df)})")

    # Fit scaler on TRAIN ONLY (includes synthetic samples)
    X_train = train_df[FEATURE_COLS].astype(np.float32).values
    scaler = fit_standard_scaler(X_train)
    save_json(out_dir / "feature_stats.json", scaler.to_json())

    # Build torch datasets
    train_ds = AsiaSweepTabularDataset(train_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler)
    val_ds = AsiaSweepTabularDataset(val_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler)
    test_ds = AsiaSweepTabularDataset(test_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler)

    train_loader = DataLoader(train_ds, batch_size=int(args.batch), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=int(args.batch), shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=int(args.batch), shuffle=False)

    hidden_sizes = tuple(int(x.strip()) for x in str(args.hidden).split(",") if x.strip())
    model = AsiaSweepMLP(
        num_numeric_features=len(FEATURE_COLS),
        num_symbols=max(1, len(symbol_map)),
        symbol_emb_dim=int(args.symbol_emb_dim),
        hidden_sizes=hidden_sizes if hidden_sizes else (64, 32),
        dropout=float(args.dropout),
        use_residual=bool(args.residual),
    ).to(device)

    # pos_weight to handle imbalance (plan)
    y_train = train_df["label"].fillna(0).astype(int).values
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    if pos > 0:
        pos_weight = torch.tensor([neg / max(1, pos)], dtype=torch.float32, device=device)
    else:
        pos_weight = torch.tensor([1.0], dtype=torch.float32, device=device)

    if args.focal_loss:
        loss_fn = FocalLossWithLogits(alpha=float(args.focal_alpha), gamma=float(args.focal_gamma), pos_weight=pos_weight)
        loss_name = "focal"
    else:
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        loss_name = "bce"
    optim = torch.optim.Adam(model.parameters(), lr=float(args.lr))

    best_val_auc = None
    best_epoch = -1
    patience_left = int(args.patience)

    model_path = out_dir / "model.pt"

    for epoch in range(1, int(args.epochs) + 1):
        tr_loss = train_epoch(model, train_loader, optim, loss_fn, device)
        val_auc, val_acc = evaluate(model, val_loader, device)
        print(f"epoch={epoch:03d} train_loss={tr_loss:.6f} val_auc={val_auc:.4f} val_acc={val_acc:.4f}")

        improved = best_val_auc is None or (val_auc == val_auc and val_auc > best_val_auc)  # val_auc==val_auc checks not-NaN
        if improved:
            best_val_auc = val_auc
            best_epoch = epoch
            patience_left = int(args.patience)
            torch.save(model.state_dict(), str(model_path))
        else:
            patience_left -= 1
            if patience_left <= 0:
                break

    # Load best model for test metrics
    if model_path.exists():
        state = torch.load(str(model_path), map_location=device)
        model.load_state_dict(state)

    test_auc, test_acc = evaluate(model, test_loader, device)
    test_rich = evaluate_rich(model, test_loader, device)
    val_rich = evaluate_rich(model, val_loader, device)

    def _finite_or_none(v):
        try:
            f = float(v)
        except Exception:
            return None
        return f if math.isfinite(f) else None

    metrics = {
        "data": str(Path(args.data)),
        "sizes": {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "best_epoch": best_epoch,
        # Keep JSON strict across languages: store None for NaN/inf when splits are empty.
        "best_val_auc": _finite_or_none(best_val_auc),
        "test_auc": _finite_or_none(test_auc),
        "test_acc": _finite_or_none(test_acc),
        "test_precision": _finite_or_none(test_rich.get("precision")),
        "test_recall": _finite_or_none(test_rich.get("recall")),
        "test_f1": _finite_or_none(test_rich.get("f1")),
        "test_confusion": test_rich.get("confusion"),
        "val_precision": _finite_or_none(val_rich.get("precision")),
        "val_recall": _finite_or_none(val_rich.get("recall")),
        "val_f1": _finite_or_none(val_rich.get("f1")),
        "val_confusion": val_rich.get("confusion"),
        "feature_cols": list(FEATURE_COLS),
        "hidden_sizes": list(hidden_sizes),
        "dropout": float(args.dropout),
        "symbol_emb_dim": int(args.symbol_emb_dim),
        "pos_weight": float(pos_weight.detach().cpu().numpy().reshape(-1)[0]),
        "loss_fn": loss_name,
        "use_residual": bool(args.residual),
        "seed": int(args.seed),
        "device": str(device),
    }
    save_json(out_dir / "metrics.json", metrics)
    print(f"Saved: {model_path}")

    # Optional: activate this artifact dir by writing <model_root>/current.json (atomic).
    try:
        root = str(args.activate_root).strip()
        if root:
            from ml.asia_sweep_london_mss.model_registry import write_current_pointer

            pointer = write_current_pointer(root, active_dir=out_dir, metrics=metrics)
            print(f"Activated: {pointer}")
    except Exception as e:
        print(f"Warning: failed to write current.json pointer: {e}")


if __name__ == "__main__":
    main()
