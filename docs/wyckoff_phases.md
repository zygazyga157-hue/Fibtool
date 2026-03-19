# Wyckoff Market Phases — Detection and Handling in Fibtool

This document explains the Wyckoff market phases and how the project's live trade/setup tools detect and treat each phase.

Overview
--------
- Wyckoff divides markets into four high-level phases: Accumulation, Markup, Distribution, and Markdown.
- The live trade setup (`live_trade_setup_bot_mt5.py`) can require Wyckoff confirmation before accepting a setup (see `--require-wyckoff` and `--wyckoff-bias`).
- The analyzer (`FibonacciSquareOfNine`) supplies a `wyckoff_analysis` object which this tool uses. Key fields used by the runner: `detected` (bool), `is_accumulation` (bool or None), and `pattern` (text descriptor).

Phases and sub-structure
------------------------
1. Accumulation (base-building)
   - Typical sequence: Preliminary Support (PS), Selling Climax (SC), Automatic Rally (AR), Secondary Test (ST), Sign of Strength (SOS), Last Point of Support (LPS).
   - Price behavior: horizontal or slightly rising range, high-volume selling absorbed by larger interests, false break-downs and quick recoveries.
   - Detection heuristics used by the tool: range-bound price structure, repeated tests of a low with diminishing downside and rising volume on rallies; `wyckoff_analysis.detected` + `is_accumulation == True`.

2. Markup (uptrend)
   - After accumulation, price breaks higher with follow-through and expanding range/volume.
   - Detection: breakout above accumulation range, rising highs and higher lows, confirmation via confluence zones and S9 analysis.

3. Distribution (top-building)
   - Typical sequence: Preliminary Supply (PSY), Buying Climax (BC), Automatic Reaction (AR), Secondary Test (ST), Sign of Weakness (SOW), Last Point of Supply (LPSY).
   - Price behavior: range near highs, large-volume spikes that fail to sustain new highs.
   - Detection heuristics: range-bound near highs with failed upsides and high-volume distribution bars; `wyckoff_analysis.detected` + `is_accumulation == False`.

4. Markdown (downtrend)
   - After distribution, price declines with follow-through and widening downside moves.
   - Detection: break below distribution range, lower lows and lower highs, confirmed by confluence and ATR expansion.

How the tool uses Wyckoff in decision logic
-------------------------------------------
- `--require-wyckoff`: when set, the `run_once` and live loop will reject trade setups unless `wyckoff_analysis.detected` is True.
- `--wyckoff-bias` options:
  - `auto`: when Wyckoff is detected, the reported `is_accumulation` determines the preferred trade side (accumulation → prefer longs, distribution → prefer shorts). If the suggested setup side does not match the Wyckoff side, the run will return `wyckoff-side-filter`.
  - `accumulation` / `distribution`: require that the detected Wyckoff phase matches the requested bias; otherwise the run returns `wyckoff-bias-filter`.
  - `any`: ignore Wyckoff phase (treat as not required).

Practical enforcement in code
----------------------------
- The runner reads the analyzer output (`analysis.get('wyckoff_analysis')`). It checks `detected` and `is_accumulation`.
- If `--require-wyckoff` and not `detected`: returns status `wyckoff-required` and skips the setup.
- If `--wyckoff-bias` is `accumulation` or `distribution` and the detected phase doesn't match: returns `wyckoff-bias-filter` with `reason` indicating mismatch.
- If `--wyckoff-bias auto` and Wyckoff detected, the tool enforces side alignment: when the detected phase implies `long` but the setup is `short`, return `wyckoff-side-filter`.

Confirmation and robustness
---------------------------
- The Wyckoff signal is considered as part of the filters — it is not the only gate. The tool also requires minimum confluences (`--min-confs`), minimum RR, slippage checks, and position/duplicate checks.
- For indecision/Doji-like signals, the project recommends using a confirmation candle rule (see `formats.txt` in the repository): wait for the next candle to close above/below the signal candle's high/low for BUY/SELL confirmation.
- Override rules: when a single strong opposing pattern exists (shortline, dark cloud cover, strong bearish Engulfing) the system may suppress a weak contrary signal — this prevents noisy trades during mixed signals.

Outputs and statuses you'll see
------------------------------
- `wyckoff-required` — a valid trade was found but Wyckoff detection was required and not present.
- `wyckoff-bias-filter` — the operator requested a specific Wyckoff bias which does not match the detected phase.
- `wyckoff-side-filter` — `--wyckoff-bias auto` detected an opposite side and the suggested setup side was not aligned.

Best practices and recommendations
---------------------------------
- Timeframe: use higher timeframe (D1) for phase detection; Wyckoff is a structural/phase concept and is most reliable on daily/weekly charts.
- Use `--require-wyckoff` during live production only after you have validated detection accuracy in dry runs.
- Use `--min-confs` to require at least 1–3 strong confluences (stronger filters reduce false signals).
- Start with `--dry-run --once` across your symbol list (see `symbols_timeframes.json`) to verify outputs before enabling live order sends.

Implementation notes for developers
----------------------------------
- The tool relies on the `FibonacciSquareOfNine.analyze_market(...)` result providing a `wyckoff_analysis` dict. If you change the analyzer's output schema, update the checks in `live_trade_setup_bot_mt5.py` accordingly.
- Consider adding a small numeric `wyckoff_confidence` score to the analyzer output so the runner can use a threshold instead of strict boolean checks.
- For multi-timeframe validation, add an optional check that requires the Wyckoff phase to be present on both the specified timeframe and a slower timeframe (e.g., D1 and W1).

Example CLI (dry-run snapshot across symbols):
```powershell
python live_trade_setup_bot_mt5.py --symbols-file symbols_timeframes.json --timeframe D1 --require-wyckoff --wyckoff-bias auto --min-confs 2 --dry-run --once
```

Questions or next steps
-----------------------
- Want the runner to produce a per-symbol `phase_report.json` summarizing detected Wyckoff phase and confidence? I can add that as a follow-up.

---
Document created by the Fibtool code assistant; keep this file alongside other docs in `docs/`.
