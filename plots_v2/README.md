# Plots V2 — Native MT5 Object Generation Engine (Fibtool)

Plots V2 upgrades Fibtool “plotting” from **drawing approximations** (V1 lines/zones) to a **native MT5 object engine** (V2):

- V1: `analysis rows -> draw lines`
- V2: `market structure -> anchors -> object specs -> MT5-native objects -> lifecycle`

This folder (`plots_v2/`) is **additive**. It does not break or replace the V1 plotting tools in `plots/`.

---

## 0) Core Idea

V2 produces two things:

1) **Object Specs** (portable, deterministic, versioned)
   - Append-only JSONL: `outputs/mt5_objects_v2.jsonl`
   - Inspection CSV: `outputs/mt5_objects_v2.csv`

2) **MT5 Scripts** that turn specs into **native chart objects**
   - `FibtoolV2_<TOOL>_<SYMBOL>_<TF>.mq5` (apply/create/update)
   - `FibtoolV2_<TOOL>_<SYMBOL>_<TF>_Cleanup.mq5` (prefix-based cleanup)

The MT5 script is the renderer. The Python tools are the object-spec generator.

---

## 1) Folder Layout

### Engine Core (shared library)

- `plots_v2/__init__.py`
  - Declares `ENGINE_VERSION` (currently `2.0.0`)

- `plots_v2/common.py`
  - Slug helpers (`symbol_slug`, `symbol_tf_slug`)
  - `outputs/` utilities
  - ISO datetime parsing (`parse_iso_dt`)
  - JSONL utilities (latest record selection)
  - Bars IO (`load_bars`)
  - ATR calc (`calc_atr`)
  - Pivot detection (`detect_pivots`)
  - Compact JSON encoding (for stable hashing and CSV embedding)

- `plots_v2/object_specs.py`
  - Typed dataclasses:
    - `AnchorPoint`
    - `ObjectLevel`
    - `ObjectContext`
    - `MT5ObjectSpec`
  - Stable `object_id` generation (`sha1` of canonical payload)
  - Persistence:
    - `append_specs()` writes JSONL + CSV (flattened)
    - `latest_batch_for()` reads “latest created_ts batch” for a symbol/timeframe

- `plots_v2/anchor_engine.py`
  - Loads bars for a `(symbol,timeframe)`
  - Detect pivots (same logic family as V1 pivot detectors)
  - Select anchors:
    - Optional Asia sweep hints from `outputs/asia_mss_signals.jsonl`
    - Otherwise last alternating pivot pair, filtered by minimum swing size (ATR-based)
  - Select ABC anchors for projection tools (`select_abc`)

- `plots_v2/mt5_object_factory.py`
  - Converts `MT5ObjectSpec` into MQL5 `ObjectCreate` + property setters
  - Supported native objects:
    - `OBJ_FIBO`
    - `OBJ_EXPANSION`
    - `OBJ_FIBOTIMES`
    - `OBJ_GANNFAN`
    - `OBJ_GANNGRID`
  - Supported generic overlays:
    - `OBJ_HLINE`
    - `OBJ_TEXT`
    - `OBJ_ARROW`
    - `OBJ_RECTANGLE`

- `plots_v2/mt5_script_generator.py`
  - Writes `.mq5` scripts into the MT5 scripts folder:
    - Apply script
    - Cleanup script
  - Prefix-based naming:
    - `fibtool_v2_<symbol>_<tf>_<object_type>_<object_id>`
  - MT5 scripts directory:
    - Uses `FIBTOOL_MT5_DATA_FOLDER` if set
    - Otherwise uses the default Terminal profile folder used by V1 tools

- `plots_v2/object_lifecycle.py`
  - Lifecycle state file:
    - `outputs/mt5_object_state_v2.json`
  - State machine:
    - `ACTIVE` (default on create)
    - `TESTED` (price touched any derived level at least once)
    - `EXPIRED` (replaced by newer object in same group OR older than TTL)
    - `BROKEN` (manual)
  - Manual lifecycle CLI helper:
    - `plots_v2/lifecycle_cli.py --mark-broken <object_id>`

### Tools (thin wrappers over engine)

- Tool 1: `plots_v2/fib_retracement_plot.py`
  - Creates `OBJ_FIBO` retracement object with custom level ratios

- Tool 2: `plots_v2/fib_projection_plot.py`
  - Creates `OBJ_EXPANSION` A–B–C expansion object

- Tool 3: `plots_v2/gann_fan_plot.py`
  - Creates `OBJ_GANNFAN` (scale from ATR or point)

- Tool 4: `plots_v2/gann_grid_plot.py`
  - Creates `OBJ_GANNGRID` (scale from ATR or point)

- Tool 5: `plots_v2/fib_time_plot.py`
  - Creates `OBJ_FIBOTIMES` (Fibonacci time zones)

- Tool 6: `plots_v2/square9_plot.py`
  - Creates S9 levels as `OBJ_HLINE` + `OBJ_TEXT`
  - Uses `fib_square_strategy.FibonacciSquareOfNine.calculate_s9_levels()`

- Tool 7 (MVP): `plots_v2/confluence_plot.py`
  - Finds confluence between fib ratios and S9 levels
  - Renders confluence as `OBJ_RECTANGLE` zone + `OBJ_TEXT` label

- Tool 8 (MVP): `plots_v2/structure_overlay_plot.py`
  - Reads `outputs/asia_mss_signals.jsonl`
  - Renders Asia range + sweep markers as overlay objects

---

## 2) Quick Start (Operator Workflow)

### Step A — Ensure bars exist

Plots V2 is offline-by-default and relies on bars stored under `outputs/`.

Expected files (any one is enough; timeframe variants are preferred):

- `outputs/<symbol>_<timeframe>_bars.csv`
- `outputs/<symbol>_bars.csv`

Examples:

- `outputs/xauusd_h1_bars.csv`
- `outputs/xauusd_bars.csv`

If you do not have bars for your symbol/timeframe, run your collector (for example `mt5_bg_collector.py`) or whichever pipeline in your repo produces the `_bars.csv` files.

### Step B — Point MT5 scripts at the correct Terminal folder

Set the MT5 terminal profile folder (recommended):

PowerShell:

```powershell
$env:FIBTOOL_MT5_DATA_FOLDER="C:\Users\<you>\AppData\Roaming\MetaQuotes\Terminal\<terminal_id>"
```

Then V2 scripts will be written to:

```
$env:FIBTOOL_MT5_DATA_FOLDER\MQL5\Scripts
```

If you don’t set `FIBTOOL_MT5_DATA_FOLDER`, V2 uses the same default path baked into the V1 tools. That may be wrong if your terminal ID differs.

### Step C — Generate a V2 script (example: Fibonacci retracement)

```powershell
python plots_v2/fib_retracement_plot.py --symbols XAUUSD --timeframes H1 --once
```

This will:

- append a spec record to `outputs/mt5_objects_v2.jsonl`
- append a row to `outputs/mt5_objects_v2.csv`
- update state in `outputs/mt5_object_state_v2.json`
- write MT5 scripts:
  - `FibtoolV2_FibRetracement_XAUUSD_H1.mq5`
  - `FibtoolV2_FibRetracement_XAUUSD_H1_Cleanup.mq5`

### Step D — Run the script inside MT5

1) In MT5, open the symbol chart (e.g., `XAUUSD`) and the correct timeframe (e.g., `H1`)
2) In Navigator → Scripts:
- run `FibtoolV2_XAUUSD_H1`
   - example: `FibtoolV2_FibRetracement_XAUUSD_H1`
3) The script creates objects on the current chart.

### Step E — Cleanup if needed

Run:

- `FibtoolV2_XAUUSD_H1_Cleanup`
   - example: `FibtoolV2_FibRetracement_XAUUSD_H1_Cleanup`

Cleanup deletes only objects whose names start with:

```
fibtool_v2_<tool>_xauusd_h1_
```

No wildcard deletion outside that prefix is used.

---

## 3) CLI Flags (All V2 Tools)

All V2 tool scripts share a consistent CLI defined in `plots_v2/cli.py`.

Common flags:

- `--symbols XAUUSD,EURUSD`
- `--timeframes H1,H4,D1`
- `--outputs-dir outputs` (default `outputs`)
- `--mt5-data-folder <path>` (overrides env var)
- `--emit-spec-only` (do not write `.mq5`)
- `--once` (run once)
- `--interval 60` (run repeatedly every N seconds)
- `--replay 2026-04-18T12:00:00Z` (as-of mode: ignore future candles/signals)
- `--pivot-left 5` / `--pivot-right 5` (pivot detection)
- `--ttl-hours 72` (lifecycle expiry)
- `--max-objects 50` (priority-based cap in generated MT5 script)

Tool-specific flags:

- `gann_fan_plot.py` / `gann_grid_plot.py`:
  - `--unit-mode atr|point`
- `square9_plot.py`:
  - `--max-levels 20`
- `confluence_plot.py`:
  - `--top-n 10`
  - `--fib-ratios "0,0.236,0.382,0.5,0.618,1,1.618"`
- `fib_projection_plot.py`:
  - `--d-levels "1.272,1.618,2.618"`
  - `--no-predict-d` (disable D markers)

Examples:

```powershell
python plots_v2/gann_fan_plot.py --symbols XAUUSD --timeframes H1 --unit-mode atr --once
python plots_v2/gann_grid_plot.py --symbols XAUUSD --timeframes H4 --unit-mode point --once
```

---

## 4) Bars Format Requirements

V2 assumes your bars CSV contains at least:

- `time`
- `open`
- `high`
- `low`
- `close`

Optional:

- `volume`
- `point`

Time parsing:

- `time` is parsed using `pandas.to_datetime(..., utc=True)`
- If `time` is missing but `timestamp` exists, V2 renames `timestamp` → `time`

Timezone:

- V2 normalizes to UTC internally.
- Specs store times as ISO strings with `+00:00` offset.

---

## 5) Anchor Selection (Anchor Engine)

Anchor selection is the most important “intelligence jump” from V1 → V2.

### 5.1 Pivot detection

`plots_v2/common.py::detect_pivots(df, left, right)` marks pivot lows/highs using a windowed min/max test:

- pivot high if its high is greater/equal than highs in the window
- pivot low if its low is lower/equal than lows in the window

Defaults:

- `left = 5`
- `right = 5`

### 5.2 Anchor confidence (candidate ranking)

`select_anchors()` ranks multiple anchor candidates and chooses the best-scoring pair. The score is built from:

- pivot quality (extremeness vs local window)
- ATR multiple (swing size)
- liquidity sweep alignment (Asia sweep hints when available)
- session weighting
- recency weighting

The chosen anchor score is surfaced in spec metadata:

- `metadata.anchor_confidence`
- `metadata.anchor_components`

### 5.3 Auto pivot anchors

When no structure hint dominates, the engine falls back to pivot pairs:

- collects all pivot points into a time-ordered list
- walks backwards to find the most recent **alternating pair**:
  - one `pivot_low`, one `pivot_high`
- filters by minimum swing size:
  - `abs(priceB - priceA) >= swing_min_atr_mult * ATR(14)`
  - default `swing_min_atr_mult = 1.5`

### 5.4 Asia sweep hint anchors (optional)

If `outputs/asia_mss_signals.jsonl` exists:

- loads the latest record for the symbol
- if `sweep_high` or `sweep_low` is true:
  - uses `asia_low` and `asia_high` as anchors
  - validates swing size (ATR-based) when ATR exists

This is a “hint” path for structure-first anchoring:

- use real session structure when available
- fall back to pivots when not

### 5.5 ABC anchors for projections

`select_abc()` searches the last 3 alternating pivots and returns:

- A–B pair (`AnchorSelection`)
- C point (`AnchorPoint`)

Used by `fib_projection_plot.py` to build expansions.

---

## 6) Object Spec Format (JSONL + CSV)

### 6.1 JSONL record structure

File:

- `outputs/mt5_objects_v2.jsonl`

Each line is one JSON record representing a full `MT5ObjectSpec`.

Fields:

- `object_id` (sha1 stable id)
- `symbol` (e.g. `XAUUSD`)
- `timeframe` (e.g. `H1`)
- `object_type` (e.g. `OBJ_FIBO`)
- `engine_version` (e.g. `2.0.0`)
- `created_ts_utc` (ISO datetime)
- `anchor_1` / `anchor_2` / `anchor_3`
  - `{ time_utc, price, kind }`
- `levels` (list of `{ value, text, color, style, width }`)
- `strength` (0..1 recommended)
- `context`
  - `{ label, sources[] }`
- `metadata` (free-form dict)

Example (trimmed):

```json
{
  "object_id": "f3e8d9...",
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "object_type": "OBJ_FIBO",
  "engine_version": "2.0.0",
  "created_ts_utc": "2026-05-20T18:02:11.123456+00:00",
  "anchor_1": {"time_utc":"2026-05-20T10:00:00+00:00","price":3300.0,"kind":"pivot_low"},
  "anchor_2": {"time_utc":"2026-05-20T16:00:00+00:00","price":3360.0,"kind":"pivot_high"},
  "levels": [{"value":0.618,"text":"61.8%","color":"","style":"","width":1}],
  "strength": 0.83,
  "context": {"label":"fib_retracement","sources":["anchor:auto_pivots"]},
  "metadata": {"ratios":[0,0.236,0.382,0.5,0.618,0.786,1,1.272,1.618],"atr":12.3,"point":0.01}
}
```

### 6.2 CSV export format

File:

- `outputs/mt5_objects_v2.csv`

Columns:

- `object_id`
- `symbol`
- `timeframe`
- `object_type`
- `engine_version`
- `created_ts_utc`
- `anchor_1_time`
- `anchor_1_price`
- `anchor_2_time`
- `anchor_2_price`
- `anchor_3_time`
- `anchor_3_price`
- `levels_json` (compact JSON string)
- `strength`
- `context` (compact JSON string)
- `metadata_json` (compact JSON string)

CSV is meant for quick grepping/inspection/spreadsheets. JSONL is the canonical store.

### 6.3 Stable object_id rules

`object_id` is:

```
sha1(
  compact_json({
    symbol,
    timeframe,
    object_type,
    engine_version,
    anchors[],
    levels[]
  })
)
```

Implications:

- Deterministic: same inputs -> same ID
- Small changes (anchors/levels/version) -> new ID
- Works across machines (no local file path dependency)

---

## 7) MT5 Script Generation

### 7.1 Apply script

`FibtoolV2_<SYMBOL>_<TF>.mq5`:

- Deletes any existing object with the exact name it is about to create
- Creates the object (`ObjectCreate`)
- Sets properties:
  - level count/values/texts for fib objects
  - scale/direction for gann objects
  - tooltip text for traceability
- Calls `ChartRedraw()`

Objects created are named:

```
fibtool_v2_<symbol>_<tf>_<object_type>_<object_id>
```

Example:

```
fibtool_v2_xauusd_h1_OBJ_FIBO_f3e8d9...
```

### 7.2 Cleanup script

`FibtoolV2_<SYMBOL>_<TF>_Cleanup.mq5`:

- Iterates over all objects on the chart
- Deletes only those whose names begin with:

```
fibtool_v2_<symbol>_<tf>_
```

This is safe, prefix-based cleanup that will not touch other objects.

### 7.3 MT5 scripts directory resolution

Python writes scripts into:

```
<MT5_DATA_FOLDER>\MQL5\Scripts
```

Where `<MT5_DATA_FOLDER>` is:

1) `--mt5-data-folder` if provided, else
2) `FIBTOOL_MT5_DATA_FOLDER` env var, else
3) default folder hard-coded to match V1 defaults

If scripts do not appear in MT5:

- verify the folder is correct
- restart MT5 or refresh the Navigator panel

---

## 8) Lifecycle State (ACTIVE / TESTED / RESPECTED / FAILED / EXPIRED / BROKEN)

File:

- `outputs/mt5_object_state_v2.json`

Each key is `object_id`, value is state metadata.

Fields:

- `object_id`
- `symbol`
- `timeframe`
- `object_type`
- `first_seen_ts`
- `last_seen_ts`
- `hit_count`
- `state` (`ACTIVE|TESTED|RESPECTED|FAILED|EXPIRED|BROKEN`)
- `group_key` (`SYMBOL|TIMEFRAME|OBJECT_TYPE`)

### 8.1 Touch detection (TESTED)

Rules:

- For `OBJ_FIBO`:
  - levels are treated as ratios between anchor A and anchor B
  - derived level price is: `A + (B-A) * ratio`
- Touch is defined as: `bar_low <= level_price <= bar_high`
- Touch window default: last 500 bars

When any level is touched at least once:

- `hit_count += 1`
- `ACTIVE -> TESTED`

### 8.1b Reaction confirmation (RESPECTED) and breaks (FAILED)

MVP heuristics (ATR-based, computed from recent bars):

- `RESPECTED`: after a touch, price moves away from the level/zone midpoint by at least `0.75 × ATR`
- `FAILED` (rectangles): after a touch, close breaks outside the zone by at least `0.25 × ATR`

### 8.2 Replacement expiry (EXPIRED)

When a new spec is created in the same group:

- `(symbol,timeframe,object_type)` is the group
- older objects in that group become `EXPIRED`

This keeps the chart from accumulating stale objects when you regenerate.

### 8.3 TTL expiry (EXPIRED)

If an object is older than:

- `--ttl-hours` (default 72)

Then it becomes `EXPIRED` (unless already BROKEN).

### 8.4 Manual broken marking (BROKEN)

To manually mark a bad object:

```powershell
python plots_v2/lifecycle_cli.py --mark-broken <object_id>
```

This only modifies `outputs/mt5_object_state_v2.json`.

---

## 17) Telemetry (Chart Ecosystem Metrics)

V2 writes a lightweight telemetry file:

- `outputs/chart_metrics.json`

Each tool run appends a snapshot (last 100) containing:

- objects created in that run
- average strength
- lifecycle state counts (if state exists)

---

## 9) Tool-by-Tool Detailed Behavior

### Tool 1 — Fibonacci Retracement (`OBJ_FIBO`)

Script:

- `plots_v2/fib_retracement_plot.py`

Inputs:

- auto anchors A/B

Default levels (ratios):

- Retrace: `0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0`
- Extension: `1.272, 1.618`

Spec fields:

- `object_type = "OBJ_FIBO"`
- `anchor_1 = A`, `anchor_2 = B`
- `levels[]` stores ratios as `value`
- `metadata["ratios"]` stores full ratio list
- `strength` is computed from:
  - swing size in ATR multiples
  - pivot kind diversity
  - recency (48h half-life)

Notes:

- MT5 interprets fib levels relative to anchor points.
- V2 writes the levels into the native fib object rather than drawing separate lines.

### Tool 2 — Fibonacci Projection/Expansion (`OBJ_EXPANSION`)

Script:

- `plots_v2/fib_projection_plot.py`

Inputs:

- auto ABC anchors (last 3 alternating pivots)

Default levels:

- `1.272, 1.618, 2.618, 4.236`

Spec fields:

- `object_type = "OBJ_EXPANSION"`
- `anchor_1=A`, `anchor_2=B`, `anchor_3=C`

Notes:

- If the engine cannot find 3 alternating pivots, it prints a clear message and skips.

### Tool 3 — Gann Fan (`OBJ_GANNFAN`)

Script:

- `plots_v2/gann_fan_plot.py`

Scale modes:

- `--unit-mode atr` (default):
  - `scale = ATR(14) * 0.25`
- `--unit-mode point`:
  - `scale = point * 100`

Direction:

- descending if anchor is `pivot_high`
- ascending otherwise

Notes:

- V2 uses a synthetic “next bar” anchor for the second time coordinate.
- This ensures the object can be created deterministically.

### Tool 4 — Gann Grid (`OBJ_GANNGRID`)

Script:

- `plots_v2/gann_grid_plot.py`

Same scale + direction rules as fan.

### Tool 5 — Fibonacci Time Zones (`OBJ_FIBOTIMES`)

Script:

- `plots_v2/fib_time_plot.py`

Default time levels:

- `1, 2, 3, 5, 8, 13, 21`

Notes:

- This introduces a “time” dimension into the charting.
- It’s a core V2 primitive for future timing confluence.

### Tool 6 — Square of Nine (`OBJ_HLINE + OBJ_TEXT`)

Script:

- `plots_v2/square9_plot.py`

How it works:

- Computes Square-of-Nine levels from the pivot price (anchor B)
- Ranks by distance to current close
- Draws top K levels (default K=20)
  - each as `OBJ_HLINE` plus a label `OBJ_TEXT`

Strength:

- higher for canonical degrees (45/90/180/360)
- higher when ATR-normalized distance is smaller

Notes:

- MT5 does not provide a “Square-of-Nine” object type; this is the correct hybrid:
  - horizontal line + label, but still native MT5 objects

### Tool 7 (MVP) — Confluence Layer (`OBJ_RECTANGLE + OBJ_TEXT`)

Script:

- `plots_v2/confluence_plot.py`

Confluence definition (MVP):

- For each fib ratio price, find nearest S9 level price.
- Confluence if:

```
abs(fib_price - s9_price) <= tolerance
```

Tolerance:

```
tolerance = max(point*5, ATR*0.15)
```

Output:

- A rectangle zone centered on the fib price with half-width = tolerance
- A label describing the confluence score and components

Confluence strength (0..100):

- degree weight (canonical degrees get bonus)
- fib weight (0.5, 0.618, 0.786, 1.0, 1.618 get bonus)
- distance penalty (ATR-normalized)

Notes:

- This is the “replacement” for V1 horizontal confluence spam.
- V2 defaults to top N confluences (N=10).

### Tool 8 (MVP) — Structure Overlay (`OBJ_RECTANGLE + OBJ_TEXT + OBJ_ARROW`)

Script:

- `plots_v2/structure_overlay_plot.py`

Input data:

- `outputs/asia_mss_signals.jsonl` (latest record per symbol)

Output:

- Asia range rectangle
- Status label
- Sweep arrows if `sweep_high` / `sweep_low`

Notes:

- MT5 lacks many structure-native objects; overlays are the correct approach here.

---

## 10) “Spec Only” Mode (Debug)

Use `--emit-spec-only` to:

- append JSONL + CSV
- update lifecycle state
- skip `.mq5` writing

Example:

```powershell
python plots_v2/confluence_plot.py --symbols XAUUSD --timeframes H1 --emit-spec-only --once
```

This is useful when:

- you want to validate anchor selection and spec generation first
- your MT5 folder isn’t set yet

---

## 11) Troubleshooting

### 11.1 “No anchors found”

Causes:

- no bars file exists for that symbol/timeframe
- too few bars
- pivot settings too strict
- swing filter too strict (ATR-based)

Fix:

- confirm you have `outputs/<symbol>_<tf>_bars.csv` or `outputs/<symbol>_bars.csv`
- try lowering pivot windows:

```powershell
python plots_v2/fib_retracement_plot.py --pivot-left 2 --pivot-right 2 --once
```

### 11.2 Scripts not showing up in MT5

Causes:

- wrong MT5 terminal profile folder
- Navigator not refreshed

Fix:

- set `FIBTOOL_MT5_DATA_FOLDER`
- confirm scripts appear under `<folder>\MQL5\Scripts`
- restart MT5 or refresh Navigator

### 11.3 Chart becomes cluttered

Fix:

- run cleanup script for that symbol/timeframe
- reduce K/top-N (currently constants inside scripts; can be made CLI options later)

### 11.4 Lifecycle is not updating to TESTED

Causes:

- not enough bars in touch window
- touch logic only implemented for certain object types (not expansion)

Fix:

- ensure bars include `high`/`low`
- treat lifecycle as a v2.0 MVP signal; refine later

---

## 12) Development Notes / Extending V2

### 12.1 Adding a new MT5 object type

Steps:

1) Extend `plots_v2/mt5_object_factory.py`:
   - add a case for `spec.object_type`
   - implement `ObjectCreate` signature
   - implement required property setters

2) Add a tool script that emits `MT5ObjectSpec` objects:
   - anchor detection
   - compute levels
   - set context + metadata
   - persist
   - optionally write scripts

### 12.2 Adding CLI configuration for constants

Right now, some knobs are constants in the tool scripts:

- `square9_plot.py` (K nearest levels)
- `confluence_plot.py` (top N confluences)
- fib ratio lists

Best next step:

- add CLI flags for:
  - `--max-levels`
  - `--top-n`
  - `--fib-ratios "0,0.236,0.382,..."`

### 12.3 Implementing “OBJ_GANNLINE”

Your plan mentions `OBJ_GANNLINE` specifically. V2.0 currently renders S9 using:

- `OBJ_HLINE` + `OBJ_TEXT`

If/when you want `OBJ_GANNLINE`:

- add a new renderer case in `mt5_object_factory.py`
- decide what “Gann line” means for your S9 representation (anchored ray? angle? slope?)

### 12.4 Improving anchor selection with MSS / liquidity events

Right now:

- “structure hint” is a minimal Asia sweep assist

Future:

- integrate BOS/MSS anchors from your Asia sweep pipeline:
  - use MSS break candle times as anchors
  - use liquidity pool eqh/eql touches as anchor candidates

---

## 13) Testing

Test file:

- `tests/test_plots_v2.py`

What it validates:

- anchor engine selects an alternating pivot pair on synthetic bars
- object_id generation is deterministic
- MQL generation contains `ObjectCreate` and the target object type

Dependency note:

- tests are skipped if `pandas` is not installed (uses `pytest.importorskip("pandas")`)

---

## 14) Roadmap (Suggested Next Improvements)

High-impact upgrades to consider next:

1) **Single unified “All-in-one V2” generator**
   - build one tool that emits a consistent set of objects:
     - retracement + fan + grid + time zones + confluence + structure overlay
   - output one script per symbol/timeframe (already supported)

2) **Object registry + “update instead of delete-create”**
   - currently scripts delete-by-name then recreate
   - upgrade to:
     - reuse existing objects by ID
     - update levels/properties in place where possible

3) **Lifecycle: real “TESTED/BROKEN” automation**
   - touch detection for expansion objects
   - broken detection heuristics (e.g., multiple breaks beyond invalidation)

4) **Confluence: multi-layer scoring**
   - incorporate:
     - Asia range
     - harmonic completion
     - DegreeFactor angles
   - unify into one “Confluence Strength” score

5) **Spec versioning / migrations**
   - keep `engine_version` stable
   - add a tiny “spec reader” that can migrate old records if needed

---

## 15) Safety & Compatibility

- V2 does not modify V1 CSV formats.
- V2 does not delete any non-V2 objects.
- Cleanup is prefix-based and requires explicit execution in MT5.
- Specs are append-only, so you can always audit history.

---

## 16) Operator Recipes (Copy/Paste)

### Generate everything V2 for one symbol/timeframe (manual run)


```powershell
# Fibonacci Retracement (custom ratios supported)
python plots_v2/fib_retracement_plot.py --symbols XAUUSD --timeframes H1 --fib-ratios "0,0.236,0.382,0.5,0.618,0.786,1,1.272,1.618" --once

# Fibonacci Projection/Expansion (custom D levels supported)
python plots_v2/fib_projection_plot.py --symbols XAUUSD --timeframes H1 --d-levels "1.272,1.618,2.618,4.236" --once

# Gann Fan
python plots_v2/gann_fan_plot.py --symbols XAUUSD --timeframes H1 --unit-mode atr --once

# Gann Grid
python plots_v2/gann_grid_plot.py --symbols XAUUSD --timeframes H1 --unit-mode atr --once

# Fibonacci Time Zones (custom time levels supported)
python plots_v2/fib_time_plot.py --symbols XAUUSD --timeframes H1 --time-levels "1,2,3,5,8,13,21" --once

# Square of Nine
python plots_v2/square9_plot.py --symbols XAUUSD --timeframes H1 --max-levels 20 --once

# Confluence Layer (custom fib ratios and top-N)
python plots_v2/confluence_plot.py --symbols XAUUSD --timeframes H1 --top-n 10 --fib-ratios "0,0.236,0.382,0.5,0.618,0.786,1,1.272,1.618" --once

# Structure Overlay
python plots_v2/structure_overlay_plot.py --symbols XAUUSD --timeframes H1 --once
```

#### Best-practice CLI flag summary

- `--fib-ratios` (Retracement, Confluence): Set custom Fibonacci ratios for retracement and confluence tools.
  Example: `--fib-ratios "0,0.236,0.382,0.5,0.618,0.786,1,1.272,1.618"`
- `--d-levels` (Projection): Set custom expansion/projection levels for ABC expansions.
  Example: `--d-levels "1.272,1.618,2.618,4.236"`
- `--time-levels` (Time Zones): Set custom Fibonacci time zone levels.
  Example: `--time-levels "1,2,3,5,8,13,21"`
- `--max-levels` (Square9): Number of S9 levels to plot.
- `--top-n` (Confluence): Number of top confluence zones to plot.
- `--unit-mode` (Gann tools): Use `atr` (default) or `point` for scaling.
- `--pivot-left`, `--pivot-right`: Tune pivot detection sensitivity for all tools.
- `--emit-spec-only`: Only emit JSONL/CSV specs, skip script generation (debug/validation).

Tune these flags for your market, timeframe, and analysis needs for maximum accuracy and insight.

### Continuous refresh every minute

```powershell
python plots_v2/confluence_plot.py --symbols XAUUSD --timeframes H1 --interval 60
```

### Mark a bad object as broken

```powershell
python plots_v2/lifecycle_cli.py --mark-broken <object_id>
```

---

If you want, the next step is to add a unified `plots_v2/v2_all.py` runner that emits a full, consistent object set in one script, using a single anchor selection pass per symbol/timeframe.
