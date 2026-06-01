from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from .common import ensure_outputs_dir, symbol_slug, symbol_tf_slug
from .mt5_object_factory import to_mql_create_lines
from .object_specs import MT5ObjectSpec, latest_batch_for, PRIORITIES


_DEFAULT_MT5_DATA_FOLDER = Path.home() / "AppData" / "Roaming" / "MetaQuotes" / "Terminal" / "D0E8209F77C8CF37AD8BF550E51FF075"


def resolve_mt5_scripts_dir(mt5_data_folder: str | None = None) -> Path:
    base = mt5_data_folder or os.environ.get("FIBTOOL_MT5_DATA_FOLDER") or str(_DEFAULT_MT5_DATA_FOLDER)
    return Path(base) / "MQL5" / "Scripts"


def _script_header(name: str) -> str:
    return f"""//+------------------------------------------------------------------+
//| {name}
//| Fibtool Plots V2 — Native MT5 Object Engine
//+------------------------------------------------------------------+
#property copyright "Fibtool"
#property version   "2.00"
#property script_show_inputs

// NOTE: `input` defaults must be compile-time constants in MQL5.
// We leave defaults empty and resolve runtime values inside `OnStart()`.
input string Symbol_Input = "";
input ENUM_TIMEFRAMES Tf_Input = PERIOD_CURRENT;

void OnStart()
{{
   long chartId = ChartID();
   string sym = (StringLen(Symbol_Input) > 0) ? Symbol_Input : Symbol();
   ENUM_TIMEFRAMES tf = Tf_Input;
   Print("[FibtoolV2] Start");
"""


def _script_footer() -> str:
    return """   ChartRedraw(chartId);
   Print("[FibtoolV2] Done");
}
"""


def generate_apply_script(
    symbol: str,
    timeframe: str,
    specs: List[MT5ObjectSpec],
    *,
    prefix: str,
    tool_label: str,
) -> str:
    tf_label = str(timeframe).upper()
    sym_label = str(symbol).upper()
    name = f"FibtoolV2_{tool_label}_{sym_label}_{tf_label}.mq5"
    out = [_script_header(name)]
    for spec in specs:
        out.extend("   " + ln for ln in to_mql_create_lines(prefix, spec))
        out.append("")
    out.append(_script_footer())
    return "\n".join(out)


def generate_cleanup_script(symbol: str, timeframe: str, *, prefix: str, tool_label: str) -> str:
    tf_label = str(timeframe).upper()
    sym_label = str(symbol).upper()
    name = f"FibtoolV2_{tool_label}_{sym_label}_{tf_label}_Cleanup.mq5"
    return f"""//+------------------------------------------------------------------+
//| {name}
//| Deletes Fibtool V2 objects for this symbol/timeframe (prefix-based)
//+------------------------------------------------------------------+
#property script_show_inputs

input bool Confirm = true;
input string ParentId8 = ""; // optional: delete only objects related to this parent (first 8 chars of parent object_id)

void OnStart()
{{
   if(!Confirm) {{ Print("[FibtoolV2] Cleanup aborted (Confirm=false)"); return; }}

   long chartId = ChartID();
   string pref = "{prefix}_";
   string ptag = (StringLen(ParentId8) > 0) ? ("_p" + ParentId8) : "";
   int total = ObjectsTotal(chartId, 0, -1);
   int removed = 0;
   for(int i = total - 1; i >= 0; i--)
   {{
      string name = ObjectName(chartId, i, 0, -1);
      if(StringFind(name, pref, 0) == 0)
      {{
         if(StringLen(ptag) > 0 && StringFind(name, ptag, 0) < 0)
            continue;
         if(ObjectDelete(chartId, name)) removed++;
      }}
   }}
   ChartRedraw(chartId);
   Print("[FibtoolV2] Removed ", removed, " objects with prefix ", pref);
}}
"""


def write_scripts(
    symbol: str,
    timeframe: str,
    specs: List[MT5ObjectSpec],
    *,
    tool_label: str,
    mt5_data_folder: str | None = None,
    max_objects: int = 50,
) -> tuple[Path, Path]:
    scripts_dir = resolve_mt5_scripts_dir(mt5_data_folder)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    sym = str(symbol).upper()
    tf = str(timeframe).upper()
    tool_slug = symbol_slug(tool_label)
    prefix = f"fibtool_v2_{tool_slug}_{symbol_slug(sym)}_{tf.lower()}"

    # Priority-based filtering to avoid chart chaos.
    # Rule: if spec count exceeds max_objects, drop LOW first, then MEDIUM until within cap.
    if max_objects and max_objects > 0 and len(specs) > int(max_objects):
        rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
        # stable sort: highest priority first, then strength desc
        specs = sorted(
            specs,
            key=lambda s: (rank.get(str(s.priority).upper(), 1), float(s.strength or 0.0)),
            reverse=True,
        )[: int(max_objects)]

    apply_name = f"FibtoolV2_{tool_label}_{sym}_{tf}.mq5"
    cleanup_name = f"FibtoolV2_{tool_label}_{sym}_{tf}_Cleanup.mq5"

    apply_path = scripts_dir / apply_name
    cleanup_path = scripts_dir / cleanup_name

    apply_path.write_text(generate_apply_script(sym, tf, specs, prefix=prefix, tool_label=tool_label), encoding="utf-8")
    cleanup_path.write_text(generate_cleanup_script(sym, tf, prefix=prefix, tool_label=tool_label), encoding="utf-8")
    return apply_path, cleanup_path


def write_latest_batch_scripts(
    outputs_dir: Path,
    symbol: str,
    timeframe: str,
    *,
    tool_label: str,
    mt5_data_folder: str | None = None,
) -> tuple[Path, Path] | None:
    batch = latest_batch_for(outputs_dir, symbol, timeframe)
    if not batch:
        return None
    return write_scripts(symbol, timeframe, batch, tool_label=tool_label, mt5_data_folder=mt5_data_folder)
