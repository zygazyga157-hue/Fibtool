python launcher.py --interval 900 --heartbeat-interval 900 --heartbeat-dest admin --max-retries 5 --backoff-base 5 --backoff-cap 300 --risk-pct 0.5 --confirm-window 8 --st-period 10 --st-multiplier 2.5 --ut-atr-coef 2.0 --ut-atr-len 10

$env:MT5_SAFE_COMMENT = "Fibtool"

-1002944534683

Add mt5.order_calc_margin wrapper + pre-trade margin check (high priority)
 Add max_total_open_risk_pct enforcement (medium-high)
 Add daily_loss_limit_pct circuit breaker (high)
 Add ATR-based dynamic risk_pct_adjustment (medium)
 Track and persist order_check & last_error into orders.csv (low, but useful)
 Add per-symbol exposure cap and correlation groups (medium)
 Implement partial-exit / trailing stop framework (lower-priority, bigger feature)

 {
  "symbols": [
    "XAUEUR",
    "XAGEUR",
    "EURCAD",
    "USDCHF",
    "BTCUSD",
    "EURJPY",
    "EURGBP",
    "EURUSD",
    "XAGUSD",
    "XAUUSD",
    "USDCAD",
    "GBPUSD",
    "AUDUSD",
    "USDJPY"
  ],
  "timeframes": [
    "M15",
    "M30",
    "H1",
    "H4",
    "D1"
  ]
}

python plots\trend_lines_plot.py --symbols "Crash 1000 Index" --once `
  --gann-unit-mode atr --gann-atr-period 14 --gann-atr-ratio 0.25 `
  --gann-tolerance 0.15 --gann-extend-labels "1x1,2x1" `
  --gann-cluster-window-min 90

  python .\plots\degree_factor_angles_plot.py --symbols XAUUSD --once --df-lows "0.175,0.35,0.525" --df-highs "0.175,0.35" --gann-unit-mode atr --gann-atr-period 14 --gann-atr-ratio 0.25 --bars-cap 270

"Boom 1000 Index, Crash 1000 Index,Boom 500 Index,Crash 500 Index,Step Index,BTCUSD,UK 100,Wall Street 30,US SP 500,US Tech 100,ETHUSD,BTCETH,SOLUSD,Volatility 25 Index,Volatility 50 Index,Volatility 75 Index"

python live_trade_setup_bot_mt5.py --symbols-file symbols_timeframes.json --timeframe D1 --require-wyckoff --wyckoff-bias auto --min-confs 2


python scripts/run_asia_sweep.py --live --no-dry-run --interval 300 --time-zone Africa/Johannesburg --session-time-zone Europe/London --risk-pct 1.0 --ml --ml-model-root outputs/models/asia_sweep_mss --ml-min-prob 0.60 --ml-retrain-at 14:15 --ml-retrain-tz Europe/London

python -m ml.asia_sweep_london_mss.train --data ml/asia_sweep_london_mss/data/dataset_v3_both.csv --out outputs/models/asia_sweep_mss/v3_20260330 --smote --focal-loss --hidden 64,32 --dropout 0.1 --patience 8 --epochs 50 --activate-root outputs/models/asia_sweep_mss

python -m ml.asia_sweep_london_mss.train_v3 --no-smote --no-residual --dropout 0.1 --hidden 64,32 --data outputs/models/asia_sweep_mss/current_dataset.csv

python -m ml.asia_sweep_london_mss.train_v3 --data outputs/models/asia_sweep_mss/current_dataset.csv --smote --residual --dropout 0.1 --hidden 128,64 --epochs 80 --batch-size 512

python -m ml.asia_sweep_london_mss.prepare_dataset --symbols EURUSD,GBPUSD,BTCUSD,US30,USDJPY,GBPJPY,USDCHF,XAUUSD,XAGUSD --both-sides --out outputs/models/asia_sweep_mss/current_dataset.csv

$env:MLFLOW_TRACKING_URI = "http://localhost:5000" ; $env:OPTUNA_STORAGE = "postgresql+psycopg2://postgres:000808@localhost:5433/optuna" ; python -m ml.asia_sweep_london_mss.optuna_search --trials 3 --study asia_v3_smoke --epochs 

"BTCUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "GBPJPY",
    "USDCHF",
    "XAUUSD",
    "XAGUSD",
    "US30"