# Plots V2 — Native MT5 Object Generation Engine

## Summary
Upgrade plotting from “draw lines from confluence rows” (V1) to a **data-driven MT5 object engine** (V2) that:
- infers **anchors** (market structure → swing points / MSS/sweep pivots),
- generates **object specifications** (typed + versioned),
- renders **MT5-native objects** (`OBJ_FIBO`, `OBJ_EXPANSION`, `OBJ_GANNFAN`, `OBJ_GANNGRID`, `OBJ_FIBOTIMES`, `OBJ_GANNLINE` + generic overlays),
- manages **object lifecycle** (ACTIVE/TESTED/EXPIRED/BROKEN),
- keeps **V1 outputs/scripts unchanged** (strict backward compatibility).

## Implementation (decision-complete)

### 1) Add a new V2 package + entry scripts
Create a new top-level folder `plots_v2/` (do not modify `plots/` V1 tools beyond docs references).

**Core modules (shared library):**
- `plots_v2/anchor_engine.py`
  - Loads bars from `outputs/<symbol>_<timeframe>_bars.csv`, fallback to `outputs/<symbol>_bars.csv`.
  - Pivot detection (reuse the V1 approach): left/right window defaults `5/5`.
  - Anchor selection default: **Auto swing anchors** = latest alternating `pivot_low` and `pivot_high` pair with minimum swing size filter.
  - Swing filter default: `abs(priceB-priceA) >= 1.5 * ATR(14)` (ATR computed from bars).
  - Optional “structure-driven anchor hints”: if `outputs/asia_mss_signals.jsonl` exists and latest record for symbol has a sweep (`sweep_high`/`sweep_low`), prefer its Asia range points as candidate anchors.

- `plots_v2/object_specs.py`
  - Define dataclasses (no new runtime deps): `AnchorPoint`, `MT5ObjectSpec`, `ObjectLevel`, `ObjectContext`.
  - Stable `object_id` generation: `sha1(symbol|timeframe|object_type|anchors|levels|engine_version)`.
  - Canonical persistence:
    - JSONL: `outputs/mt5_objects_v2.jsonl` (append-only; each line is one `MT5ObjectSpec`).
    - CSV export: `outputs/mt5_objects_v2.csv` (flattened for inspection; JSON fields stored as compact JSON strings).

  **CSV columns (fixed, matches your new paradigm):**
  - `object_id`, `symbol`, `timeframe`, `object_type`, `engine_version`, `created_ts_utc`
  - `anchor_1_time`, `anchor_1_price`, `anchor_2_time`, `anchor_2_price`, `anchor_3_time`, `anchor_3_price`
  - `levels_json`, `strength`, `context`, `metadata_json`

- `plots_v2/mt5_object_factory.py`
  - Converts `MT5ObjectSpec` → MQL5 `ObjectCreate(...)` + property setters.
  - Support object types:
    - `OBJ_FIBO`: sets `OBJPROP_LEVELS`, `OBJPROP_LEVELVALUE`, `OBJPROP_LEVELTEXT`, optional rays.
    - `OBJ_EXPANSION`: uses A–B–C anchors; sets levels (127.2/161.8/261.8/423.6 default).
    - `OBJ_FIBOTIMES`: sets Fibonacci time ratios (1,2,3,5,8,13,21 default).
    - `OBJ_GANNFAN`: sets `OBJPROP_SCALE` and `OBJPROP_DIRECTION`.
    - `OBJ_GANNGRID`: sets `OBJPROP_SCALE` and `OBJPROP_DIRECTION`.
    - `OBJ_GANNLINE`: used for Square-of-Nine projections when a native object fits; otherwise fallback to `OBJ_HLINE` + `OBJ_TEXT` label pair (still “native objects”, just generic).
    - Overlay primitives for structure/confluence: `OBJ_RECTANGLE`, `OBJ_TEXT`, `OBJ_ARROW`.

- `plots_v2/mt5_script_generator.py`
  - Generates two scripts per symbol/timeframe:
    - `FibtoolV2_<SYMBOL>_<TF>.mq5` (creates/updates objects from latest spec batch)
    - `FibtoolV2_<SYMBOL>_<TF>_Cleanup.mq5` (deletes only objects with prefix `fibtool_v2_<SYMBOL>_<TF>_`)
  - Reads latest “batch” by `created_ts_utc` for that symbol/timeframe from `mt5_objects_v2.jsonl` (not lexicographic string max; parse as datetime like `asia_sweep_plot.py` does).
  - Object naming in MT5 (cleanup-safe):
    - `fibtool_v2_<symbol>_<tf>_<object_type>_<object_id>`
  - Default MT5 scripts directory:
    - Use env var first: `FIBTOOL_MT5_DATA_FOLDER`; else reuse the V1 pattern.

- `plots_v2/object_lifecycle.py`
  - State file: `outputs/mt5_object_state_v2.json`
  - Per `object_id` track:
    - `first_seen_ts`, `last_seen_ts`, `hit_count`, `state`
  - State transitions (explicit rules):
    - `ACTIVE` on first creation.
    - `TESTED` when price touches any level/zone at least once (touch rule: `low <= level <= high` on any bar since creation; use last N=500 bars).
    - `EXPIRED` when either:
      - a newer object of same `(symbol,timeframe,object_type)` is generated with different anchors, OR
      - `age_hours > 72` (default TTL; configurable CLI flag).
    - `BROKEN` reserved for later; in V2.0 only set manually via a small CLI action `--mark-broken <object_id>` (keeps logic deterministic while engine matures).

### 2) Implement the V2 tools (as thin wrappers over the core)
Each tool: (a) detect anchors, (b) create `MT5ObjectSpec` records, (c) persist JSONL/CSV, (d) generate `.mq5` script(s).

- `plots_v2/fib_retracement_plot.py` (V2 Tool 1)
  - Output: `OBJ_FIBO`
  - Anchors: swing A (time,price) to swing B (time,price)
  - Default fib levels (customizable):
    - Retrace: `0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0`
    - Extensions: `1.272, 1.618` (rendered as additional levels on the same object)
  - Strength score (0–1): combine swing size (ATR-multiples), pivot quality (distance from local extremes), and recency weighting.

- `plots_v2/fib_projection_plot.py` (V2 Tool 2)
  - Output: `OBJ_EXPANSION`
  - Anchors: A–B–C structure derived from last 3 alternating pivots; if not available, skip with a clear log message and produce no spec.
  - Default expansion levels: `1.272, 1.618, 2.618, 4.236` (stored as ratios; MT5 uses them directly via level properties).

- `plots_v2/gann_fan_plot.py` (V2 Tool 3)
  - Output: `OBJ_GANNFAN`
  - Anchor: pivot point from anchor engine; second time anchor = next bar time (ensures fan exists).
  - Scale computation (deterministic):
    - Default mode `atr`: `scale = ATR(14) * 0.25` (matches your existing “unit per bar” logic).
    - Optional `point` mode: `scale = point * 100`.
  - Direction: ascending if anchor is pivot_low, descending if pivot_high.

- `plots_v2/gann_grid_plot.py` (V2 Tool 4)
  - Output: `OBJ_GANNGRID`
  - Same scale + direction rules as fan.
  - Anchors: pivot time/price + second anchor time (next bar).

- `plots_v2/fib_time_plot.py` (V2 Tool 5)
  - Output: `OBJ_FIBOTIMES`
  - Anchors: swing A→B (time anchors), price can be `0` where the object expects it.
  - Default time ratios: `1,2,3,5,8,13,21` (stored in spec; applied via MT5 properties).

- `plots_v2/square9_plot.py` (V2 Tool 6)
  - Uses your existing Square-of-Nine math from `fib_square_strategy.py`:
    - compute S9 levels from pivot price for degrees `[22.5..720]` and their negatives
  - Render strategy:
    - Primary: create `OBJ_HLINE` per level + `OBJ_TEXT` label showing degree and origin.
    - Grouping: generate only the top K nearest levels around current price (default K=20) to avoid chart spam.
  - Strength: higher for canonical degrees (45/90/180/360) and closer distance to current price (ATR-normalized).

- `plots_v2/confluence_engine.py` + `plots_v2/confluence_plot.py` (V2 Tool 7 MVP)
  - MVP confluence definition (implementable now):
    - Confluence when a Fib level price is within `tolerance = max(point*5, ATR*0.15)` of an S9 level price.
  - Output object: `OBJ_RECTANGLE` “zone” centered on the confluence price (width = tolerance) + `OBJ_TEXT` label “Confluence Strength: NN”.
  - Confluence strength score (0–100):
    - Base = fib weight + s9 degree weight + distance penalty (ATR-normalized)
    - Optional bonus if latest Asia sweep signal exists and confluence lies within Asia range zone.

- `plots_v2/structure_overlay.py` (V2 Tool 8 MVP)
  - Reuse `outputs/asia_mss_signals.jsonl` structure (already parsed in V1).
  - Draw:
    - Asia range rectangle (`OBJ_RECTANGLE`) + labels (`OBJ_TEXT`)
    - Sweep markers (`OBJ_ARROW`) when `sweep_high/low`
    - MSS/BOS labels (generic text objects)

### 3) CLI + ergonomics
All V2 tool scripts accept:
- `--symbols XAUUSD,EURUSD`
- `--timeframes H1,H4` (optional; if absent, look for non-timeframe bars first)
- `--once` or `--interval <sec>` (match V1 operator experience)
- `--mt5-data-folder <path>` overrides env var for portability
- `--emit-spec-only` (skip writing `.mq5`, just write JSONL/CSV) for debugging

### 4) Documentation updates (no breaking changes)
- Update `plots/README.md` to add a **Plots V2** section:
  - what V2 is (object engine),
  - where it outputs (`outputs/mt5_objects_v2.*`),
  - how to run each V2 tool,
  - how cleanup works (prefix-based).

## Test Plan
Add pytest coverage focused on determinism + schema integrity:
- Anchor engine:
  - given a small synthetic bars fixture, detects pivots and selects anchors deterministically.
- Object spec:
  - stable `object_id` for same inputs; different anchors produce different IDs.
  - JSONL round-trip: `spec -> json -> spec` preserves fields.
- MQL generator:
  - generated script contains `ObjectCreate(...,OBJ_FIBO,...)` / `OBJ_GANNFAN` / `OBJ_GANNGRID` depending on spec types.
  - cleanup script deletes by prefix only (no wildcard deletion outside V2 prefix).

## Assumptions / Defaults
- **Strict compatibility** honored: V1 scripts and CSVs remain as-is; V2 is additive.
- Bars source for anchors is **`outputs/*_bars.csv`** (MT5 live fetch is out of scope for initial V2 unless already present).
- Default pivot detection: left/right `5/5`, min swing `1.5 * ATR(14)`.
- V2 lifecycle uses a simple, deterministic touch-based `TESTED` rule and time-based TTL; `BROKEN` is manual in V2.0.
