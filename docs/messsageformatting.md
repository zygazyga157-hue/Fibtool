python launcher.py --interval 300 --heartbeat-interval 900 --heartbeat-dest admin --max-retries 5 --backoff-base 5 --backoff-cap 300 --risk-pct 1.0 --confirm-window 12 --st-period 10 --st-multiplier 3 --ut-atr-coef 2 --ut-atr-len 2 --allow-multiple

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
