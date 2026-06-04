Optuna + MLflow quickstart (local Postgres) for Asia Sweep V3

Overview
- This project supports hyperparameter search using Optuna with Postgres RDB storage and MLflow tracking.
- No Docker: use your local Postgres instance at `postgres:000808@localhost:5433`.

Environment variables (example PowerShell):

```powershell
$env:MLFLOW_TRACKING_URI = "http://localhost:5000"
$env:OPTUNA_STORAGE = "postgresql+psycopg2://postgres:000808@localhost:5433/optuna"
$env:MLFLOW_S3_ENDPOINT_URL = "http://localhost:9000"  # if using MinIO/S3
$env:AWS_ACCESS_KEY_ID = "minio"
$env:AWS_SECRET_ACCESS_KEY = "minio123"
```

Install dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install optuna mlflow psycopg2-binary
```

Run a smoke Optuna study (20 trials):

```powershell
python -m ml.asia_sweep_london_mss.optuna_search --trials 20 --study asia_v3_smoke
```

Notes
- `optuna_search.py` calls `train_v3.py` as a subprocess and expects it to write `outputs/asia_sweep_london_mss/last_val.json` with `val_auc`.
- For tighter integration, refactor `train_v3.py` to accept hyperparams and log to MLflow directly (we can help with that refactor).

Promotion
- After reviewing MLflow UI, promote the best run by copying the artifact directory to `outputs/models/asia_sweep_mss/v3_<stamp>` and updating `current.json` via `model_registry.write_current_pointer()`.

Security
- Keep Postgres credentials secure. Use OS-level user permissions and regular backups of the `optuna` DB.

Troubleshooting
- If Optuna cannot connect: ensure Postgres accepts connections on port 5433 and the `optuna` DB exists.
- If MLflow UI unreachable: ensure MLflow server is running and listening on `MLFLOW_TRACKING_URI`.

For help automating the full MLflow + Optuna integration (MLflow run inside training, artifact logging, distributed workers), ask me to refactor `train_v3.py` and create a `promote_model.py` tool.