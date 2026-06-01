# Fibtool Production Plot Tools

Production-ready plotting tools for MT5 confluence visualization.

## Overview

Each tool focuses on a specific visualization type:
- **Tool 1**: Horizontal Lines - Clean horizontal lines with labels
- **Tool 2**: Vertical Lines - Time markers at confluence detection
- **Tool 3**: Rectangle Zones - Filled zones around confluence levels
- **Tool 4**: Trend Lines - Diagonal lines connecting pivots to confluences
- **Tool 5**: Asia Sweep Plot - Asia ranges, Fib levels, and liquidity pools

## Plots V2 (Native MT5 Objects)

Plots V2 is an additive engine in `plots_v2/` that generates **MT5-native objects** from
data-driven object specs (anchors + levels) and writes `.mq5` scripts into your MT5
`MQL5/Scripts` folder.

**Outputs**
- Object specs (append-only): `outputs/mt5_objects_v2.jsonl`
- Inspection CSV: `outputs/mt5_objects_v2.csv`
- Lifecycle state: `outputs/mt5_object_state_v2.json`

**MT5 Scripts Path**
- Uses env var `FIBTOOL_MT5_DATA_FOLDER` when set (recommended).
- Otherwise uses the same default MT5 profile folder as V1 tools.

**Run examples**
```bash
python plots_v2/fib_retracement_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/fib_projection_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/gann_fan_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/gann_grid_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/fib_time_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/square9_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/confluence_plot.py --symbols XAUUSD --timeframes H1 --once
python plots_v2/structure_overlay_plot.py --symbols XAUUSD --timeframes H1 --once
```

**Debug**
- Use `--emit-spec-only` to skip `.mq5` generation and only write spec files.

**Cleanup**
- Each V2 run also writes a cleanup script named `FibtoolV2_<SYMBOL>_<TF>_Cleanup.mq5`.
- Cleanup deletes only objects whose names start with `fibtool_v2_<symbol>_<tf>_`.

## Tool 1: Horizontal Lines Plot

### Features
- ✅ Horizontal lines at exact confluence prices
- ✅ Text labels with confluence information
- ✅ Color-coded by side (red=resistance, blue=support)
- ✅ Quality-based line width (1-3px)
- ✅ No cleanup - preserves chart objects
- ✅ Clean, minimal design

### Usage

**Generate scripts once:**
```bash
python plots/horizontal_lines_plot.py --symbols XAUUSD --once
```

**Generate for multiple symbols:**
```bash
python plots/horizontal_lines_plot.py --symbols XAUUSD,USDCAD --once
```

**Continuous mode (auto-refresh):**
```bash
python plots/horizontal_lines_plot.py --symbols XAUUSD --interval 60
```

**Generate cleanup scripts:**
```bash
python plots/horizontal_lines_plot.py --symbols XAUUSD --cleanup
```

### Execution in MT5

1. Open MT5 terminal
2. Open the target symbol chart (e.g., XAUUSD H1)
3. Navigator → Scripts → `FibtoolHorizontalLines_XAUUSD`
4. Drag script to chart or double-click

### Object Naming

All objects are prefixed with `fibtool_hline_` followed by:
- Symbol name (e.g., `XAUUSD`)
- Confluence ID
- Timestamp

Example: `fibtool_hline_XAUUSD_conf123_20251021T091602Z`

### Cleanup

To remove all horizontal line objects from a chart:
1. Run the cleanup script: `FibtoolHorizontalLines_XAUUSD_Cleanup`
2. Or manually delete via Ctrl+B → Select objects → Delete

## Tool 2: Vertical Lines Plot

### Features
- ✅ Vertical lines at exact confluence detection timestamps
- ✅ Marks key time events on chart
- ✅ Color-coded by side (red=resistance, blue=support)
- ✅ Quality-based line width and style (1-3px)
- ✅ Time labels at top of chart
- ✅ No cleanup - preserves chart objects
- ✅ Clean, minimal design

### Usage

**Generate scripts once:**
```bash
python plots/vertical_lines_plot.py --symbols XAUUSD --once
```

**Generate for multiple symbols:**
```bash
python plots/vertical_lines_plot.py --symbols XAUUSD,USDCAD --once
```

**Continuous mode (auto-refresh):**
```bash
python plots/vertical_lines_plot.py --symbols XAUUSD --interval 60
```

**Generate cleanup scripts:**
```bash
python plots/vertical_lines_plot.py --symbols XAUUSD --cleanup
```

### Execution in MT5

1. Open MT5 terminal
2. Open the target symbol chart (e.g., XAUUSD H1)
3. Navigator → Scripts → `FibtoolVerticalLines_XAUUSD`
4. Drag script to chart or double-click

### Object Naming

All objects are prefixed with `fibtool_vline_` followed by:
- Symbol name (e.g., `XAUUSD`)
- Confluence ID
- Timestamp

Example: `fibtool_vline_XAUUSD_conf123_20251021T091602Z`

### Use Cases

- Mark exact moments when confluences formed
- Identify time-based patterns
- Combine with horizontal lines for full picture
- Track confluence detection frequency over time

## Tool 3: Rectangle Zones Plot

### Features
- ✅ Filled rectangle zones spanning time range
- ✅ Visual zones for support/resistance areas
- ✅ Color-coded: Light red (resistance) / Light blue (support)
- ✅ Quality-based transparency (stronger = more opaque)
- ✅ Default 0.1% zone size around confluence price
- ✅ Spans 100 bars back, 200 bars forward
- ✅ No cleanup - preserves chart objects
- ✅ Clean, minimal design

### Usage

**Generate scripts once:**
```bash
python plots/rectangle_zones_plot.py --symbols XAUUSD --once
```

**Generate for multiple symbols:**
```bash
python plots/rectangle_zones_plot.py --symbols XAUUSD,USDCAD --once
```

**Continuous mode (auto-refresh):**
```bash
python plots/rectangle_zones_plot.py --symbols XAUUSD --interval 60
```

**Generate cleanup scripts:**
```bash
python plots/rectangle_zones_plot.py --symbols XAUUSD --cleanup
```

### Execution in MT5

1. Open MT5 terminal
2. Open the target symbol chart (e.g., XAUUSD H1)
3. Navigator → Scripts → `FibtoolRectangleZones_XAUUSD`
4. Drag script to chart or double-click

### Object Naming

All objects are prefixed with `fibtool_zone_` followed by:
- Symbol name (e.g., `XAUUSD`)
- Confluence ID
- Timestamp

Example: `fibtool_zone_XAUUSD_conf123_20251021T091602Z`

### Use Cases

- Create visual zones for support/resistance areas
- Highlight price ranges where reaction is expected
- Combine with Tool 1 (lines) for precise level + zone view
- Background shading for clearer chart reading

## Tool 4: Trend Lines Plot

### Features
- ✅ Diagonal trend lines from pivot points to confluences
- ✅ Shows relationship between historical pivots and current levels
- ✅ Color-coded by side (red=resistance, blue=support)
- ✅ Quality-based line width and style (1-3px, solid/dash)
- ✅ Labels at midpoint showing Fib percentage
- ✅ Uses pivot_low for support, pivot_high for resistance
- ✅ No cleanup - preserves chart objects
- ✅ Clean, minimal design

### Usage

**Generate scripts once:**
```bash
python plots/trend_lines_plot.py --symbols XAUUSD --once
```

**Generate for multiple symbols:**
```bash
python plots/trend_lines_plot.py --symbols XAUUSD,USDCAD --once
```

**Continuous mode (auto-refresh):**
```bash
python plots/trend_lines_plot.py --symbols XAUUSD --interval 60
```

**Generate cleanup scripts:**
```bash
python plots/trend_lines_plot.py --symbols XAUUSD --cleanup
```

### Execution in MT5

1. Open MT5 terminal
2. Open the target symbol chart (e.g., XAUUSD H1)
3. Navigator → Scripts → `FibtoolTrendLines_XAUUSD`
4. Drag script to chart or double-click

### Object Naming

All objects are prefixed with `fibtool_trend_` followed by:
- Symbol name (e.g., `XAUUSD`)
- Confluence ID
- Timestamp

Example: `fibtool_trend_XAUUSD_conf123_20251021T091602Z`

## Tool 5: Asia Sweep Plot

### Features
- ✅ **Two Styles**: `--style clean` (default) or `--style rich`
- ✅ **Clean Mode**: Minimal lines + tooltips + one-line status label
- ✅ **Rich Mode**: Status panel, zones, and deeper diagnostics
- ✅ **MSS Threshold Lines**: Optional dashed prev3 high/low triggers
- ✅ **Rich Extras**: Asia range zone, entry alert zone, current price marker
- ✅ **Clean Extras**: Sweep markers + relevant-only fib lines
- ✅ **Interactive Tooltips**: Details on hover

### Usage

**Generate scripts once:**
```bash
python plots/asia_sweep_plot.py --symbols EURUSD --style clean --once
```

**Generate for multiple symbols:**
```bash
python plots/asia_sweep_plot.py --symbols EURUSD,GBPUSD --style clean --once
```

**Generate rich scripts (debug):**
```bash
python plots/asia_sweep_plot.py --symbols EURUSD --style rich --once
```

**Generate cleanup scripts:**
```bash
python plots/asia_sweep_plot.py --symbols EURUSD --cleanup
```

### Execution in MT5

1. Open MT5 terminal
2. Open the target symbol chart (e.g., EURUSD M5)
3. Navigator → Scripts → `FibtoolAsiaSweep_eurusd` (symbol slug: lowercase, non-alnum -> `_`)
4. Drag script to chart or double-click

### Object Naming

All objects are prefixed with `fibtool_asia_` followed by:
- Symbol slug (e.g., `eurusd`)
- Element type (`asia_high`, `asia_low`, `entry`)

Example: `fibtool_asia_eurusd_asia_high`

### Notes

- The overlay performs a clean redraw for the symbol by deleting objects that start with its prefix.
- You can override the MT5 data folder path using `FIBTOOL_MT5_DATA_FOLDER` if your terminal ID differs.

### Use Cases

- Visualize Asia session ranges and liquidity pools
- Mark Fibonacci entry levels for qualified trades
- Identify EQH/EQL clusters with touch counts
- Combine with other tools for complete strategy visualization

## Design Principles

1. **Single Responsibility**: Each tool does one thing well
2. **No Unscoped Cleanup**: Tools only delete objects they own (by prefix) when redraw/cleanup is requested
3. **Minimal Dependencies**: Uses only standard libraries + MetaTrader5
4. **Production Ready**: Clean code, error handling, logging
5. **Multi-Symbol Support**: Works with any symbol from confluence data

## Development

### Adding New Plot Tools

1. Create new file: `plots/[tool_name]_plot.py`
2. Use unique object prefix: `fibtool_[toolname]_`
3. Follow the same structure as `horizontal_lines_plot.py`
4. Update this README with tool documentation

### Testing

```bash
# Test with once mode first
python plots/horizontal_lines_plot.py --symbols XAUUSD --once

# Check generated script
ls "C:\Users\DELL\AppData\Roaming\MetaQuotes\Terminal\...\MQL5\Scripts"

# Execute in MT5 and verify
# Check Experts tab for logs
# Use Ctrl+B to view objects
```

## File Structure

```
plots/
├── README.md                          # This file
├── horizontal_lines_plot.py           # Tool 1: Horizontal lines
├── vertical_lines_plot.py             # Tool 2: Vertical time markers
├── rectangle_zones_plot.py            # Tool 3: Filled zones
├── trend_lines_plot.py                # Tool 4: Diagonal trend lines
├── asia_sweep_plot.py                 # Tool 5: Asia sweep elements
```

## Notes

- Tools 1-4 read from `outputs/{symbol}_confluences.csv`
- Tool 5 reads from `outputs/asia_mss_signals.csv`
- Scripts are saved to MT5's Scripts folder
- Tools preserve existing chart objects
- Each tool has its own cleanup script
