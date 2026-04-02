# ML Overview

This folder contains machine-learning experiments and helpers for the Fibtool project.

Subfolders:

- `asia_sweep_london_mss/` — Full dataset preparation, PyTorch datasets, models and training scripts for the Asia Sweep (London MSS) strategy. See the detailed docs and quickstart inside that folder.

Quick link:

- Asia Sweep ML docs: asia_sweep_london_mss/README.md

If you moved ML code to a specific subfolder, keep that pattern: place per-strategy experiments in dedicated subfolders and include a `README.md` explaining the exact steps to reproduce datasets and experiments.

Recommended next steps:

- Run `ml/asia_sweep_london_mss/prepare_dataset.py` to generate datasets.
- Use `ml/asia_sweep_london_mss/train.py` to train the plan-aligned model and write artifacts to `outputs/models/asia_sweep_mss/v1`.
- `train_seq.py` is kept as legacy/experimental (not plan-aligned).
