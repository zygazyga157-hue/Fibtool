# Executive Summary

Integrating candlestick-pattern signals into the Asia Sweep strategy can materially improve trade selection by adding **behavioral clues** to the structural price-action setup.  In practice, candlestick patterns are best used as *confirmation signals* or feature inputs to an ML classifier rather than standalone triggers.  For example, Lin *et al.* demonstrate that machine-learning models using multi-day candlestick pattern features can achieve high returns (Sharpe ≈0.81) on Chinese stock data.  Similarly, Mann’s analysis finds that combining multiple candlestick patterns (rather than trading them in isolation) yields **significantly stronger predictive power**.  Thus our goal is to add candlestick-derived features (pattern flags, ages, strengths, context) into the Asia Sweep ML model to boost its hit rate and edge.  

We will assemble an **expanded feature set** including:  
- **Candlestick features**: one-hot flags for detected patterns (engulfing, MSS candle, etc.), pattern “age” (bars since pattern), pattern strength/weight, displacement-candle measurements, and relative location to nearby support/resistance.  
- **Structural features**: existing Asia Sweep features (Asia-session high/low, sweep size, MSS “strength score”, Fib 0.71 distance, ATR, volatility, time-of-day, session labels, etc.).  
- **Volume/tick features**: tick or volume bars, recent volume surge indicators, order flow proxies (e.g. uptick/downtick count).  
- **Regime features**: market context indicators (e.g. trending vs range, bull/bear label, volatility regime) to condition the model on macro behavior.  
- **Engineered interactions**: logical combinations (pattern present * near support, pattern * high volume, etc.) to capture context-specific signals.  

To build the model we will curate **tick/minute-level OHLCV data** (from exchange APIs or data vendors) and **historical trade logs**. Each potential Asia Sweep trigger will be labeled (binary or ordinal) based on subsequent price movement or profit outcome.  We will ensure ample sample size (tens of thousands of examples) and address class imbalance (using stratified sampling or techniques like SMOTE) so that positive (profitable) and negative outcomes are well represented.  

We will then compare a range of models, from **interpretable to complex**:

| Model                | Pros                                             | Cons                                                 | Training Time       | Feature Importance Method          |
|----------------------|--------------------------------------------------|------------------------------------------------------|---------------------|------------------------------------|
| **Logistic Regression** | Simple, very fast; outputs calibrated probabilities; easily interpretable weights. Good baseline for linear relationships. | Can underfit nonlinearly separable data; sensitive to irrelevant features; assumes additive effects. | Very fast (seconds) | Coefficients (global); easily inspected |
| **Random Forest**      | Captures nonlinearity/interactions; robust to outliers and irrelevant features. Works well with medium-sized data.  | Can overfit if trees are deep; ensemble of many trees can be slow at predict time; model size can be large. | Moderate (minutes) | Mean decrease in impurity or permutation importance |
| **XGBoost / LightGBM** | Gradient boosting often yields top accuracy on tabular data. Handles missing data; many tunable hyperparameters. LightGBM is extremely fast on large data. | XGBoost is slower/heavier than LightGBM; both require careful tuning. Interpretability is moderate (tree-based). | Slow-Moderate (minutes–hours) | Built-in feature importance (gain/fscore), and SHAP values for global/local importance |
| **CatBoost**          | Built-in support for categorical features; less parameter tuning needed; robust default settings. | Training can be slower than LightGBM; still a black box (requires tools for interpretation). | Moderate (minutes) | Feature importance via built-in metrics or SHAP |
| **Simple NN (MLP)**   | Can capture complex nonlinear relationships; flexible. Potential to incorporate interactions automatically. | Requires much more data; easy to overfit; black-box (needs SHAP/LIME); tuning (architecture, regularization) is complex. | Slow (minutes–hours) | Difficult; can use SHAP or permutation importance, but less transparent |
| **LSTM/Transformer**  | Models sequential/time-series patterns directly; can use raw candle sequences. | Very data-hungry; long training times; high risk of overfitting; usually not needed for low-frequency signals. | Very slow (hours–days) | Even less transparent; saliency or attention maps (hard) |

We will test **hyperparameter ranges** for each: e.g. logistic (regularization C), trees (n_estimators≈50–500, max_depth 3–8, learning_rate≈0.01–0.3), NN (layers 1–3, 32–128 nodes, dropout 0–50%).  We will use **time-series cross-validation** (rolling or expanding windows) rather than random splits to preserve chronological order.  In practice this means a *walk-forward* scheme: train on e.g. the first 70% of data, test on next 10%, then roll forward, over many folds.  All modeling must enforce strict “no lookahead” – only past data features can predict future outcomes.

For **evaluation metrics**, we will combine classification stats (accuracy, precision, recall, F1, ROC-AUC, PR-AUC) with trading metrics (net PnL, Sharpe ratio, max drawdown).  For example, high ROC-AUC or PR-AUC indicates the model distinguishes good vs bad setups, but we will also simulate a backtest: e.g. only take trades when predicted probability > threshold, then apply stop/take rules and measure edge.  We will examine calibration: a good model’s predicted probabilities should align with empirical win rates (a reliability diagram).  Proper calibration is important if we use probabilities for position sizing.  

To verify the candlestick features add value, we will perform **ablation tests**: train the model *with* and *without* the candlestick-derived features, and compare performance metrics.  We will require that any improvement is statistically significant (e.g. higher mean ROC-AUC or profit, with p<0.05, using paired t-test or bootstrap confidence intervals on multiple time folds).  We might also use permutation tests to ensure the uplift isn’t due to chance.  As an example, one would expect at least a few percent lift in ROC-AUC or Sharpe ratio to justify the extra complexity.  

 *Figure 1: **ROC curve example** (AUC=0.77) illustrating the trade-off between true positive rate (TPR) and false positive rate (FPR) for a binary classifier.  A higher area under this curve indicates better discrimination.*  

 *Figure 2: **Precision-Recall curve** (blue) for a binary classifier (Linear SVC, AP=0.91) with chance-level baseline (dashed).  High precision and recall (area) indicate a strong model, which is especially informative when classes are imbalanced.*  

 *Figure 3: **Calibration plot (reliability diagram)** for example classifiers.  The closer a model’s curve is to the diagonal line, the better its predicted probabilities are calibrated.  Here the isotonic regression on Naive Bayes (purple) becomes nearly diagonal, showing well-calibrated outputs.*  

## Feature Engineering

- **Candlestick Pattern Features.**  For each candidate setup, we compute standard TA-Lib or custom candlestick detectors (engulfing, morning star, MSS candle, hammer, etc.). We include **binary flags** for each pattern detected, and also numeric “pattern strength” weights or scores.  We record the **pattern age** (how many bars have elapsed since the pattern appeared) and the pattern’s location relative to recent HTF support/resistance levels (e.g. percentage distance to nearest pivot).  We also extract characteristics of the **displacement candle** (the candle immediately following the sweep, which often indicates buy/sell pressure): its size (body and wick relative to ATR), direction, and volume.  (Lin *et al.* use multi-day pattern features as predictive inputs.)  Empirical research shows that **pattern combinations** carry more signal than singles, so we may also include counts of overlapping patterns or co-occurrence flags.

- **Asia Sweep Structural Features.** These include:
  - **Sweep size:** the distance (in pips or ATR multiples) from the Asia high/low to the sweep level.  
  - **MSS score:** a metric of the mid-session strength (how far price moved after sweep).  
  - **Fibonacci distance:** distance to the 0.618–0.786 retrace entry level.  
  - **Volatility:** recent ATR or standard deviation.  
  - **Session context:** time of day (hour of sweep), day-of-week, holiday flag, and volatility regime (quiet vs active session).  
  - **Trend/regime features:** e.g. slope of HTF moving averages, broader index trend, etc., which may modulate the efficacy of a reversal.  

- **Volume and Order-Flow Features.**  We incorporate recent volume metrics (absolute, relative to ATR, or tick-based proxies). For FX, tick count over the pattern candle or sweep candle is a loose proxy for activity. We might also include *imbalance* measures (e.g. difference between up-ticks vs down-ticks) if available.  These help filter patterns that occur on thin volume vs strong commitment.

- **Market Regime Features.**  We classify the current regime (bull/bear/high-volatility/low-volatility) using market breadth or volatility indicators.  For example, a weak reversal signal in a strong bull market might be ignored.  Including such regime labels or continuous trend scores allows the model to adapt its decision boundary.

- **Feature Interactions.**  We plan explicit interaction terms that might capture meaningful situations.  For example: “Hammer at strong support” (pattern_flag AND distance_to_support < threshold), or “Engulfing * high volume”.  Empirically, decision-tree models will partially capture these interactions, but explicitly engineering key ones can help simpler models.

## Data Requirements and Labeling

- **Data Sources.** We require high-quality historical price data for each instrument (FX, indices, etc.) at a resolution at least intrabar to catch candlestick details (e.g. 1-minute or tick bars).  Sources might include exchange APIs (e.g. Binance for crypto, OANDA/Dukascopy for FX) or bulk data (Tick Data, IQFeed, etc.).  Historical trade logs (actual executed trades by the Asia Sweep system) are very valuable for labeling outcomes and verifying slippage assumptions.  We will store data in a time-indexed format (e.g. CSV or Parquet files with timestamps, OHLCV).

- **Label Creation.**  We label each potential entry (sweep+MSS event) based on the subsequent price movement.  For a classification model, we might set the label as **1 = trade meets profit target (or profit > 0)** and **0 = otherwise**.  Alternatively, one can create multi-class or regression targets (profit amount, or classes for strong win/weak win/loss).  The label lookahead window should match the expected holding period (e.g. 4–8 hours).  We will avoid lookahead bias by constructing labels only from data available after entry.  

- **Class Balance and Sample Size.**  Profitable trades may be relatively rare (<10–20%), so we expect an imbalanced dataset.  We will collect a large sample (tens of thousands of signals) across years and instruments to ensure statistical power.  Techniques like stratified sampling or balanced batch training can address imbalance.  In some cases we may generate synthetic minority examples (SMOTE) or use class-weighting.  

- **Data Splitting.**  We split data chronologically, not randomly, to preserve time order.  For example: 70% oldest data for training, 10% validation (tuning), 20% most recent as holdout test.  We will also perform rolling “walk-forward” splits over multiple time slices to verify stability.  

## Model Candidates and Comparison

We will train and compare several models as above.  Table 1 summarizes pros/cons:

| Model                | Pros                                                                             | Cons                                                    | Training Time       | Feature Importance            |
|----------------------|----------------------------------------------------------------------------------|---------------------------------------------------------|---------------------|-------------------------------|
| **Logistic Regression** | - Very fast to train and predict<br>- Coefficients are easily interpretable<br>- Probabilities are inherently calibrated (with log-loss) | - Assumes linear separability<br>- Must manually engineer interactions<br>- Can underperform on complex patterns | Very short (seconds) | Coefficients (global importance) |
| **Random Forest**      | - Captures nonlinearity and interactions<br>- Robust to outliers/noise<br>- Minimal data prep needed | - Can be slow with many trees<br>- Larger model size<br>- Feature importance can be biased to categorical | Moderate (minutes) | Mean decrease in Gini or SHAP |
| **XGBoost**           | - Often highest predictive accuracy on structured data<br>- Handles missing data<br>- Regularization to prevent overfit | - Training is slower and more memory-intensive<br>- Many hyperparameters to tune<br>- Less interpretable than linear models | Slow (minutes–hours) | Gain-based importance, SHAP |
| **LightGBM**          | - Very fast training, especially on large datasets<br>- Good accuracy with less tuning | - Can overfit if not tuned (leaf-wise growth)<br>- Less proven in small-data regime | Fast (minutes)      | Gain-based, SHAP              |
| **CatBoost**          | - Excellent with categorical inputs (handles them natively)<br>- Robust default parameters<br>- Reduced overfitting via ordered boosting | - Slower training than LightGBM<br>- Feature importance similar challenges to other GBMs | Moderate (minutes)   | Gain, SHAP                     |
| **Neural Network (MLP)** | - Flexible nonlinear modeling<br>- Can incorporate many features and interactions | - Data-hungry; requires careful tuning<br>- Black-box (harder to interpret)<br>- Prone to overfitting without much data | Slow (minutes–hours)  | No inherent method (use SHAP/LIME/permutation) |
| **LSTM/Transformer**  | - Can use raw sequential inputs (e.g. last N candles) to potentially capture dynamics<br>- Powerful on large datasets | - Very slow training<br>- Large risk of overfitting<br>- Very opaque (difficult to audit) | Very slow (hours–days) | Very difficult; attention weights (transformer) |

Table 1: Comparison of candidate classifiers for pattern-based trade prediction.

In practice, tree-ensemble models (XGBoost/LightGBM) are often a sweet spot for tabular trading data.  We will start with XGBoost or LightGBM as baselines, then test CatBoost and a logistic model (for interpretability) and possibly a small neural net.  We will use tools like SHAP values or built-in feature importance to understand which features drive predictions.

## Training, Validation, and Testing Strategy

- **Cross-Validation:** We will employ **rolling-window (walk-forward) validation**.  For example, train on 2018–2020, validate on 2021Q1, then roll forward to train on 2018–Q2 2021, test on Q3 2021, etc.  This mimics live trading and avoids lookahead.  At least 5–10 folds should be used.  Alternatively, we can use `TimeSeriesSplit` or custom expanding window splits in sklearn.  

- **Hyperparameter Search:** For each model, we will tune hyperparameters via grid search or Bayesian optimization on the validation folds.  Key ranges include:
  - *Logistic*: regularization strength C in [0.01, 1, 100], penalty type (L1/L2).  
  - *XGBoost/LightGBM*: n_estimators (50–300), max_depth (3–7), learning_rate (0.01–0.3), min_child_weight/leaf, subsample (0.5–1.0).  
  - *CatBoost*: iterations (100–500), depth (4–10), learning_rate (0.01–0.1).  
  - *Neural Net*: layers (1–3), units (32–128), learning_rate (1e-3–1e-1), dropout (0–0.5).  
  We will monitor validation metrics to avoid overfitting (early stopping).  

- **Evaluation Metrics:** In addition to ROC-AUC and PR-AUC, we will compute accuracy, precision/recall, and F1 at a chosen threshold.  Critically, we will simulate the actual strategy returns: e.g. apply predicted signals to past data (with proper replay), include realistic **transaction costs and slippage** (e.g. 0.1–0.2% per trade as in [25†L80-L84]) and measure net PnL, Sharpe ratio, drawdown.  We will compare the upgraded model’s Sharpe against the baseline Asia Sweep Sharpe.  We will also check *calibration*: e.g. Brier score and reliability curves to ensure probability outputs are meaningful.  

- **Ablation Tests:** We will run controlled experiments where one feature group is removed.  For example:
  - All candlestick-derived features vs. none (to measure incremental lift)  
  - Only candlestick features vs. only structural features  
  - Removing volume features, etc.  
  We expect that adding candlestick flags should improve precision (fewer false signals) even if recall drops slightly.  We will test significance of any gain using statistical tests (paired t-test on fold results, or bootstrap confidence intervals) and set a threshold (e.g. p<0.05).  As a guide, an uplift of a few percentage points in ROC-AUC or a 10–20% lift in Sharpe would be considered meaningful.

## Deployment & Monitoring

Once a model is selected, we will integrate it into the live system with a proper feature pipeline. This entails:

- **Real-time Feature Pipeline:**  In production, we must compute all features on incoming data (e.g. 1m bars).  Candlestick pattern detection requires looking at recent candles; structural features need computing the current Asia high/low and fib levels on the fly.  This pipeline must run with low latency (millisecond–second scale) to issue a trade decision soon after the LMS candle completes.  

- **Latency & Throughput:**  Because predictions are needed only at sweep/MSS events (infrequent), latency is not as tight as high-frequency signals.  Even a prediction latency of a few hundred ms is likely acceptable, but we will benchmark and optimize as needed (use a compiled or vectorized implementation for pattern detection, or pre-compute heavy stats offline).

- **Feature Drift Detection:**  Market conditions change. We will implement monitoring of feature distributions (e.g. Kolmogorov-Smirnov tests) and model outputs. Alerts will be triggered if, for instance, the distribution of key features (like pattern frequency or volatility) shifts substantially, or if prediction rates move outside historical bounds.  

- **Retraining Cadence:**  We will periodically retrain the model. Initially, we might retrain monthly or when significant new data is available.  The retraining process should be automated and versioned.  Before each live update, the new model will be tested on holdout data (or an A/B run) to confirm performance.  

- **A/B Testing:**  We may run the new ML-driven strategy in parallel (paper trades) alongside the old rule-based system to gather performance stats.  Compare PnL, win rate, and adverse scenario performance to ensure no regression.

- **Logging & Alerts:**  All signals, decisions, and PnL outcomes should be logged.  Real-time dashboards can track monthly Sharpe, hit ratio, and drawdowns.  Alerts should be set for large deviations (e.g. drawdown > X%, or monthly return below -Y%).  

## Implementation Roadmap

1. **Data Collection:** Assemble a clean dataset of historical Asia sweep events with OHLCV (tick/1m) and actual outcomes. Fetch from APIs or databases.  
2. **Feature Extraction Module:** Code feature calculators for candlestick patterns, position relative to support/resistance, volume surges, etc. Validate pattern detection accuracy (plot examples).  
3. **Baseline Model:** Train current Asia Sweep model (without candlesticks) to establish baseline metrics (ROC-AUC, Sharpe).  
4. **Augmented Model:** Add candlestick features and retrain. Use the same cross-validation as baseline for fair comparison.  
5. **Feature Importance Analysis:** Compute feature importances (e.g. SHAP) to verify which patterns carry weight. Drop any unhelpful patterns if needed.  
6. **Backtesting:** Run walk-forward backtests applying the new model’s signals, include costs/slippage. Compare PnL and Sharpe to baseline.  
7. **Statistical Validation:** Perform paired tests on cross-val results to confirm any performance difference is significant (e.g. >95% confidence).  
8. **Stress Tests:** Verify model performance across different regimes (high vol vs low vol, bull vs bear). Check worst-case drawdowns.  
9. **Production Pipeline:** Deploy feature extraction and model scoring code in the trading system.  
10. **Monitoring Setup:** Implement dashboards and alerts for live tracking of model health and drift.

## Prioritized Action Checklist

- [ ] **Gather Data:** Historical 1m/tick data, trade logs for Asia Sweep signals; label outcomes.  
- [ ] **Feature Engineering:** Implement candlestick detectors (e.g. using TA-Lib) and compute all proposed features (candles, structural, volume, regime). Unit-test each.  
- [ ] **Baseline Assessment:** Train existing model; record performance metrics as baseline.  
- [ ] **Train ML Models:** Experiment with XGBoost, LightGBM, RandomForest, Logistic, etc. Tune hyperparameters with time-series CV.  
- [ ] **Compare Models:** Create a summary table of model performance (e.g. ROC-AUC, Sharpe) and feature importance rankings.  
- [ ] **Ablation Study:** Quantify lift from candlestick features (compute p-values or confidence intervals). Remove any detrimental features.  
- [ ] **Validation Metrics:** Plot ROC and PR curves (e.g. Figure 1–2), calibration curve (Figure 3), and report Brier score.  
- [ ] **Backtest with Costs:** Incorporate realistic transaction costs/slippage and simulate PnL for the new strategy. Ensure profitability after fees.  
- [ ] **Deploy to Staging:** Integrate the model into a test environment; run in parallel with paper trades.  
- [ ] **Monitoring Plan:** Implement real-time monitoring (feature drift, hit rate, PnL). Define retraining triggers and schedule.  

By following this plan, we will rigorously evaluate the benefit of candlestick features in the Asia Sweep model and ensure a robust, statistically sound enhancement to the trading system.  

**Sources:** We draw on algorithmic trading best practices and published research on candlestick-based ML models. Our evaluation uses standard metrics (ROC/PR, Sharpe) and visualization techniques to ensure transparency and performance.