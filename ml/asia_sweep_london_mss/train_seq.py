import argparse
import os
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ml.asia_sweep_london_mss.sequence_dataset import SequenceAsiaDataset
from ml.asia_sweep_london_mss.lstm_model import LSTMClassifier


def train_epoch(model, loader, optim, loss_fn, device):
    model.train()
    total_loss = 0.0
    total = 0
    correct = 0
    for xb, yb in loader:
        xb = xb.to(device).float()
        # yb: -1/0/1 -> map to binary positive (1) vs rest
        yb_raw = yb
        yb = (yb_raw > 0).float().to(device)
        optim.zero_grad()
        logits = model(xb)
        loss = loss_fn(logits, yb)
        loss.backward()
        optim.step()
        total_loss += float(loss.item()) * xb.size(0)
        preds = (torch.sigmoid(logits) > 0.5).long()
        correct += int((preds == yb.long()).sum().item())
        total += xb.size(0)
    return total_loss / total, correct / total if total else 0.0


def eval_epoch(model, loader, loss_fn, device):
    model.eval()
    total_loss = 0.0
    total = 0
    correct = 0
    with torch.no_grad():
        for xb, yb in loader:
            xb = xb.to(device).float()
            yb_raw = yb
            yb = (yb_raw > 0).float().to(device)
            logits = model(xb)
            loss = loss_fn(logits, yb)
            total_loss += float(loss.item()) * xb.size(0)
            preds = (torch.sigmoid(logits) > 0.5).long()
            correct += int((preds == yb.long()).sum().item())
            total += xb.size(0)
    return total_loss / total, correct / total if total else 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', required=True)
    p.add_argument('--batch', type=int, default=128)
    p.add_argument('--epochs', type=int, default=10)
    p.add_argument('--seq', type=int, default=12)
    p.add_argument('--horizon', type=int, default=12)
    p.add_argument('--out', default='ml/models')
    args = p.parse_args()

    ds = SequenceAsiaDataset(args.symbol, seq_len=args.seq, horizon=args.horizon)
    n = len(ds)
    nv = int(n * 0.2)
    nt = n - nv
    train_ds, val_ds = torch.utils.data.random_split(ds, [nt, nv])
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, collate_fn=lambda x: (torch.stack([item[0] for item in x]), torch.tensor([item[1] for item in x])))
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, collate_fn=lambda x: (torch.stack([item[0] for item in x]), torch.tensor([item[1] for item in x])))

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    sample_x, _ = ds[0]
    model = LSTMClassifier(input_size=sample_x.shape[1], hidden_size=64)
    model.to(device)

    optim = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()

    Path(args.out).mkdir(parents=True, exist_ok=True)

    best_val = None
    for epoch in range(1, args.epochs + 1):
        tr_loss, tr_acc = train_epoch(model, train_loader, optim, loss_fn, device)
        val_loss, val_acc = eval_epoch(model, val_loader, loss_fn, device)
        print(f"Epoch {epoch:03d}  train_loss={tr_loss:.5f} train_acc={tr_acc:.4f}  val_loss={val_loss:.5f} val_acc={val_acc:.4f}")

        if best_val is None or val_loss < best_val:
            best_val = val_loss
            torch.save(model.state_dict(), os.path.join(args.out, f'{args.symbol}_lstm_best.pt'))


if __name__ == '__main__':
    main()
