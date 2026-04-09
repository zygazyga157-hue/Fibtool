"""V3 training entry-point.

Identical save/activate flow to train.py (V1):
  - Produces the same four artifact files:
      model.pt  |  metrics.json  |  feature_stats.json  |  symbol_map.json
  - Updates current.json pointer via --activate-root (atomic write)

Differences from V1:
  - Output directory auto-stamped as  v3_{YYYYMMDD}_{HHMMSS}  unless --out is set.
  - Better defaults: focal loss ON, residual connections ON, SMOTE ON,
    higher dropout (0.3), deeper network (128,64,32), more patience (15).
  - Default dataset: ml/asia_sweep_london_mss/data/dataset_v3_both.csv
  - Default activate-root: outputs/models/asia_sweep_mss

Usage (retrain + auto-activate):
    python -m ml.asia_sweep_london_mss.train_v3

Custom data or hyperparams:
    python -m ml.asia_sweep_london_mss.train_v3 \\
        --data path/to/dataset.csv \\
        --hidden 128,64,32 \\
        --dropout 0.3 \\
        --epochs 100

Disable focal loss or SMOTE:
    python -m ml.asia_sweep_london_mss.train_v3 --no-focal-loss --no-smote
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


# ── project root on sys.path (same logic as train.py) ─────────────────────────
def _ensure_project_root_on_path() -> None:
    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


_ensure_project_root_on_path()

# ── re-use all shared training utilities from train.py ────────────────────────
from ml.asia_sweep_london_mss.train import (  # noqa: E402
    FocalLossWithLogits,
    evaluate,
    evaluate_rich,
    roc_auc_score,
    run_cv,
    set_seeds,
    train_epoch,
)
from ml.asia_sweep_london_mss.model import AsiaSweepMLP  # noqa: E402
from ml.asia_sweep_london_mss.torch_dataset import (  # noqa: E402
    FEATURE_COLS,
    AsiaSweepTabularDataset,
    build_symbol_map,
    fit_standard_scaler,
    load_dataset_csv,
    save_json,
    smote_oversample,
    time_based_split,
)


# ── V3 default paths ───────────────────────────────────────────────────────────
_DEFAULT_DATA = "ml/asia_sweep_london_mss/data/dataset_v3_both.csv"
_DEFAULT_ROOT = "outputs/models/asia_sweep_mss"


def _auto_out_dir(model_root: str) -> str:
    """Return v3_{YYYYMMDD}_{HHMMSS} under model_root (UTC timestamp)."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return str(Path(model_root) / f"v3_{stamp}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Train V3 Asia Sweep MSS classifier (auto-timestamped output)",
    )
    ap.add_argument(
        "--data",
        default=_DEFAULT_DATA,
        help=f"Dataset CSV (default: {_DEFAULT_DATA})",
    )
    ap.add_argument(
        "--out",
        default="",
        help="Output directory for artifacts. Empty = auto-stamp as v3_{YYYYMMDD}_{HHMMSS} under --activate-root.",
    )
    ap.add_argument(
        "--activate-root",
        default=_DEFAULT_ROOT,
        help=f"Model root; auto-stamps --out here and writes current.json (default: {_DEFAULT_ROOT})",
    )
    # ── training hyperparams (V3 defaults are tuned for lower overfitting) ─────
    ap.add_argument("--epochs",        type=int,   default=100)
    ap.add_argument("--batch",         type=int,   default=256)
    ap.add_argument("--lr",            type=float, default=1e-3)
    ap.add_argument("--hidden",        default="128,64,32")
    ap.add_argument("--dropout",       type=float, default=0.3)
    ap.add_argument("--symbol-emb-dim", type=int,  default=8)
    ap.add_argument("--val-frac",      type=float, default=0.15)
    ap.add_argument("--test-frac",     type=float, default=0.15)
    ap.add_argument("--patience",      type=int,   default=15)
    ap.add_argument("--seed",          type=int,   default=1337)
    ap.add_argument("--device",        default="", help="cpu|cuda|auto (default auto)")
    # ── focal loss (on by default in V3) ──────────────────────────────────────
    ap.add_argument("--focal-loss",    action="store_true",  default=True,  dest="focal_loss")
    ap.add_argument("--no-focal-loss", action="store_false",               dest="focal_loss")
    ap.add_argument("--focal-alpha",   type=float, default=0.25)
    ap.add_argument("--focal-gamma",   type=float, default=2.0)
    # ── SMOTE (on by default in V3) ───────────────────────────────────────────
    ap.add_argument("--smote",         action="store_true",  default=True,  dest="smote")
    ap.add_argument("--no-smote",      action="store_false",               dest="smote")
    ap.add_argument("--smote-ratio",   type=float, default=0.35)
    # ── residual connections (on by default in V3) ────────────────────────────
    ap.add_argument("--residual",      action="store_true",  default=True,  dest="residual")
    ap.add_argument("--no-residual",   action="store_false",               dest="residual")
    # ── cross-validation (optional) ───────────────────────────────────────────
    ap.add_argument("--cv-folds",      type=int,   default=0,
                    help="Time-series CV folds (0=disabled, use single train/val/test split)")

    args = ap.parse_args()

    set_seeds(int(args.seed))

    # ── resolve output directory ───────────────────────────────────────────────
    root = str(args.activate_root).strip()
    out_path = str(args.out).strip()
    if not out_path:
        if not root:
            root = _DEFAULT_ROOT
        out_path = _auto_out_dir(root)

    out_dir = Path(out_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"V3 output dir : {out_dir}")
    print(f"Dataset       : {args.data}")

    df = load_dataset_csv(args.data)

    # ── device ────────────────────────────────────────────────────────────────
    dev_str = str(args.device).strip().lower()
    if dev_str == "cpu":
        device = torch.device("cpu")
    elif dev_str == "cuda":
        device = torch.device("cuda")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ── optionally run CV evaluation only ─────────────────────────────────────
    if int(args.cv_folds) > 0:
        print(f"Running {args.cv_folds}-fold time-series cross-validation…")
        cv_results = run_cv(args, df, device)
        save_json(out_dir / "cv_metrics.json", cv_results)
        print(f"\nSaved CV metrics: {out_dir / 'cv_metrics.json'}")
        return

    # ── symbol map ────────────────────────────────────────────────────────────
    symbol_map = build_symbol_map(df["symbol"].tolist())
    save_json(out_dir / "symbol_map.json", symbol_map)

    # ── time-based split (no leakage) ─────────────────────────────────────────
    train_df, val_df, test_df = time_based_split(
        df, val_frac=float(args.val_frac), test_frac=float(args.test_frac)
    )

    # ── SMOTE on train only ────────────────────────────────────────────────────
    if args.smote:
        n_pos_before = int((train_df["label"] == 1).sum())
        train_df = smote_oversample(
            train_df, list(FEATURE_COLS), target_ratio=float(args.smote_ratio)
        )
        n_pos_after = int((train_df["label"] == 1).sum())
        print(f"SMOTE: {n_pos_before} → {n_pos_after} positives in train (total {len(train_df)})")

    # ── scaler fitted on train only ───────────────────────────────────────────
    X_train = train_df[FEATURE_COLS].astype(np.float32).values
    scaler = fit_standard_scaler(X_train)
    save_json(out_dir / "feature_stats.json", scaler.to_json())

    # ── datasets & loaders ────────────────────────────────────────────────────
    train_ds = AsiaSweepTabularDataset(
        train_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler
    )
    val_ds = AsiaSweepTabularDataset(
        val_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler
    )
    test_ds = AsiaSweepTabularDataset(
        test_df, feature_cols=FEATURE_COLS, symbol_map=symbol_map, scaler=scaler
    )

    train_loader = DataLoader(train_ds, batch_size=int(args.batch), shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=int(args.batch), shuffle=False)
    test_loader  = DataLoader(test_ds,  batch_size=int(args.batch), shuffle=False)

    # ── model ─────────────────────────────────────────────────────────────────
    hidden_sizes = tuple(
        int(x.strip()) for x in str(args.hidden).split(",") if x.strip()
    ) or (128, 64, 32)

    model = AsiaSweepMLP(
        num_numeric_features=len(FEATURE_COLS),
        num_symbols=max(1, len(symbol_map)),
        symbol_emb_dim=int(args.symbol_emb_dim),
        hidden_sizes=hidden_sizes,
        dropout=float(args.dropout),
        use_residual=bool(args.residual),
    ).to(device)

    # ── loss function ─────────────────────────────────────────────────────────
    y_train = train_df["label"].fillna(0).astype(int).values
    pos = int((y_train == 1).sum())
    neg = int((y_train == 0).sum())
    pos_weight = (
        torch.tensor([neg / max(1, pos)], dtype=torch.float32, device=device)
        if pos > 0
        else torch.tensor([1.0], dtype=torch.float32, device=device)
    )

    if args.focal_loss:
        loss_fn = FocalLossWithLogits(
            alpha=float(args.focal_alpha),
            gamma=float(args.focal_gamma),
            pos_weight=pos_weight,
        )
        loss_name = "focal"
    else:
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        loss_name = "bce"

    optim = torch.optim.Adam(model.parameters(), lr=float(args.lr))

    # ── training loop ─────────────────────────────────────────────────────────
    best_val_auc: Optional[float] = None
    best_epoch = -1
    patience_left = int(args.patience)
    model_path = out_dir / "model.pt"

    for epoch in range(1, int(args.epochs) + 1):
        tr_loss = train_epoch(model, train_loader, optim, loss_fn, device)
        val_auc, val_acc = evaluate(model, val_loader, device)
        print(
            f"epoch={epoch:03d}  train_loss={tr_loss:.6f}  "
            f"val_auc={val_auc:.4f}  val_acc={val_acc:.4f}"
        )

        improved = best_val_auc is None or (val_auc == val_auc and val_auc > best_val_auc)
        if improved:
            best_val_auc = val_auc
            best_epoch = epoch
            patience_left = int(args.patience)
            torch.save(model.state_dict(), str(model_path))
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"Early stop at epoch {epoch} (patience exhausted)")
                break

    # ── load best checkpoint for evaluation ───────────────────────────────────
    if model_path.exists():
        model.load_state_dict(torch.load(str(model_path), map_location=device))

    test_auc, test_acc = evaluate(model, test_loader, device)
    test_rich = evaluate_rich(model, test_loader, device)
    val_rich  = evaluate_rich(model, val_loader,  device)

    def _finite_or_none(v: object) -> Optional[float]:
        try:
            f = float(v)  # type: ignore[arg-type]
        except Exception:
            return None
        return f if math.isfinite(f) else None

    metrics = {
        "data":           str(Path(args.data)),
        "sizes":          {"train": len(train_df), "val": len(val_df), "test": len(test_df)},
        "best_epoch":     best_epoch,
        "best_val_auc":   _finite_or_none(best_val_auc),
        "test_auc":       _finite_or_none(test_auc),
        "test_acc":       _finite_or_none(test_acc),
        "test_precision": _finite_or_none(test_rich.get("precision")),
        "test_recall":    _finite_or_none(test_rich.get("recall")),
        "test_f1":        _finite_or_none(test_rich.get("f1")),
        "test_confusion": test_rich.get("confusion"),
        "val_precision":  _finite_or_none(val_rich.get("precision")),
        "val_recall":     _finite_or_none(val_rich.get("recall")),
        "val_f1":         _finite_or_none(val_rich.get("f1")),
        "val_confusion":  val_rich.get("confusion"),
        "feature_cols":   list(FEATURE_COLS),
        "hidden_sizes":   list(hidden_sizes),
        "dropout":        float(args.dropout),
        "symbol_emb_dim": int(args.symbol_emb_dim),
        "pos_weight":     float(pos_weight.detach().cpu().numpy().reshape(-1)[0]),
        "loss_fn":        loss_name,
        "use_residual":   bool(args.residual),
        "seed":           int(args.seed),
        "device":         str(device),
    }
    save_json(out_dir / "metrics.json", metrics)

    print(f"\nSaved: {model_path}")
    print(
        f"Results → best_val_auc={best_val_auc:.4f}  "
        f"test_auc={test_auc:.4f}  test_acc={test_acc:.4f}"
    )
    print(
        f"         precision={test_rich.get('precision', 0):.4f}  "
        f"recall={test_rich.get('recall', 0):.4f}  "
        f"f1={test_rich.get('f1', 0):.4f}"
    )

    # ── optionally activate by writing current.json ───────────────────────────
    root_str = str(args.activate_root).strip()
    if root_str:
        try:
            from ml.asia_sweep_london_mss.model_registry import write_current_pointer

            pointer = write_current_pointer(root_str, active_dir=out_dir, metrics=metrics)
            print(f"Activated  : {pointer}")
        except Exception as exc:
            print(f"Warning: failed to write current.json pointer: {exc}")


if __name__ == "__main__":
    main()
