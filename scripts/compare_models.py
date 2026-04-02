"""Compare model metrics across versions."""
import json
import os
import sys

root = "outputs/models/asia_sweep_mss"
versions = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))

for name in versions:
    mp = os.path.join(root, name, "metrics.json")
    if not os.path.exists(mp):
        continue
    m = json.load(open(mp))
    print(f"=== {name} ===")
    print(f"  sizes:          {m.get('sizes')}")
    print(f"  best_epoch:     {m.get('best_epoch')}")
    print(f"  best_val_auc:   {m.get('best_val_auc')}")
    print(f"  test_auc:       {m.get('test_auc')}")
    print(f"  test_acc:       {m.get('test_acc')}")
    print(f"  test_precision: {m.get('test_precision', 'N/A')}")
    print(f"  test_recall:    {m.get('test_recall', 'N/A')}")
    print(f"  test_f1:        {m.get('test_f1', 'N/A')}")
    print(f"  test_confusion: {m.get('test_confusion', 'N/A')}")
    print(f"  val_precision:  {m.get('val_precision', 'N/A')}")
    print(f"  val_recall:     {m.get('val_recall', 'N/A')}")
    print(f"  val_f1:         {m.get('val_f1', 'N/A')}")
    print(f"  val_confusion:  {m.get('val_confusion', 'N/A')}")
    print(f"  loss_fn:        {m.get('loss_fn', 'bce')}")
    print(f"  features:       {len(m.get('feature_cols', []))}")
    print()
