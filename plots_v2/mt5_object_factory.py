from __future__ import annotations

from typing import List

from .object_specs import MT5ObjectSpec, ObjectLevel


def _mql_str(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def _mql_datetime_iso_to_string_to_time_expr(iso: str) -> str:
    # Convert ISO like 2026-05-20T08:00:00+00:00 -> "2026.05.20 08:00"
    try:
        # safe subset conversion without importing datetime parsing here
        s = iso.replace("Z", "").replace("+00:00", "")
        date, time = s.split("T", 1)
        hhmm = time[:5]
        y, m, d = date.split("-", 2)
        return f'StringToTime("{y}.{m}.{d} {hhmm}")'
    except Exception:
        return 'TimeCurrent()'


def object_name(prefix: str, spec: MT5ObjectSpec) -> str:
    # Include parent hint in name so parent deletes can cascade (prefix-based), while staying deterministic.
    # We keep it short to avoid MT5 name length issues.
    parent_hint = ""
    try:
        if spec.parent_object_id:
            parent_hint = f"_p{str(spec.parent_object_id)[:8]}"
    except Exception:
        parent_hint = ""
    return f"{prefix}_{spec.object_type}{parent_hint}_{spec.object_id}"


def _metadata_text(spec: MT5ObjectSpec, key: str) -> str:
    try:
        value = spec.metadata.get(key, "")
    except Exception:
        value = ""
    if value is None:
        return ""
    return str(value).strip()


def build_mt5_description(spec: MT5ObjectSpec) -> str:
    """Compact production description for MT5's object description field."""
    description = _metadata_text(spec, "description")
    if description:
        return description
    label = str(spec.context.label or "").strip()
    if label:
        return label.replace("_", " ").upper()
    return f"{spec.symbol} {spec.timeframe} {spec.object_type}"


def build_mt5_tooltip(spec: MT5ObjectSpec) -> str:
    """Compact hover text from production metadata, avoiding internal object names."""
    lines: list[str] = [build_mt5_description(spec)]

    confidence = _metadata_text(spec, "confidence")
    score = _metadata_text(spec, "confidence_score")
    if confidence and score:
        lines.append(f"Confidence: {score} ({confidence})")
    elif confidence:
        lines.append(f"Confidence: {confidence}")
    elif score:
        lines.append(f"Confidence: {score}")

    for label, key in (
        ("Bias", "trade_bias"),
        ("Reaction", "expected_reaction"),
        ("Risk", "risk_note"),
        ("Engine", "generated_by"),
    ):
        value = _metadata_text(spec, key)
        if value:
            lines.append(f"{label}: {value}")

    if len(lines) == 1:
        lines.append(f"{spec.symbol} {spec.timeframe} {spec.object_type}")
    return "\n".join(lines)


def _mql_description_tooltip_lines(
    obj_name: str,
    *,
    description: str,
    tooltip: str,
    set_text: bool = True,
) -> list[str]:
    lines: list[str] = []
    if set_text:
        lines.append(f'ObjectSetString(chartId, "{obj_name}", OBJPROP_TEXT, "{_mql_str(description)}");')
    lines.append(f'ObjectSetString(chartId, "{obj_name}", OBJPROP_TOOLTIP, "{_mql_str(tooltip)}");')
    return lines


def to_mql_create_lines(prefix: str, spec: MT5ObjectSpec) -> List[str]:
    """Return MQL5 lines that create/configure the object for a spec."""
    name = object_name(prefix, spec)
    obj_type = spec.object_type
    lines: list[str] = []

    # anchors
    a1 = spec.anchor_1
    a2 = spec.anchor_2
    a3 = spec.anchor_3

    description = build_mt5_description(spec)
    tooltip = build_mt5_tooltip(spec)
    comment = _mql_str(description)

    if obj_type == "OBJ_FIBO":
        if not (a1 and a2):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        p1 = a1.price
        p2 = a2.price
        lines.append(f'// {comment}')
        lines.append(f'ObjectDelete(chartId, "{name}");')
        lines.append(f'if(!ObjectCreate(chartId, "{name}", OBJ_FIBO, 0, {t1}, {p1}, {t2}, {p2}))')
        lines.append('{ Print("✗ create OBJ_FIBO failed: ", GetLastError()); }')
        lines.append('else {')
        # levels
        lines.extend(_mql_set_levels(name, spec.levels))
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_RAY_LEFT, false);')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_RAY_RIGHT, true);')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_HIDDEN, false);')
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append('}')
        return lines

    if obj_type == "OBJ_EXPANSION":
        if not (a1 and a2 and a3):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        t3 = _mql_datetime_iso_to_string_to_time_expr(a3.time_utc)
        p1 = a1.price
        p2 = a2.price
        p3 = a3.price
        lines.append(f'// {comment}')
        lines.append(f'ObjectDelete(chartId, "{name}");')
        lines.append(f'if(!ObjectCreate(chartId, "{name}", OBJ_EXPANSION, 0, {t1}, {p1}, {t2}, {p2}, {t3}, {p3}))')
        lines.append('{ Print("✗ create OBJ_EXPANSION failed: ", GetLastError()); }')
        lines.append('else {')
        lines.extend(_mql_set_levels(name, spec.levels))
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);')
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append('}')
        return lines

    if obj_type == "OBJ_FIBOTIMES":
        if not (a1 and a2):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        # price anchors are required for ObjectCreate signature; use the anchor prices.
        p1 = a1.price
        p2 = a2.price
        lines.append(f'// {comment}')
        lines.append(f'ObjectDelete(chartId, "{name}");')
        lines.append(f'if(!ObjectCreate(chartId, "{name}", OBJ_FIBOTIMES, 0, {t1}, {p1}, {t2}, {p2}))')
        lines.append('{ Print("✗ create OBJ_FIBOTIMES failed: ", GetLastError()); }')
        lines.append('else {')
        lines.extend(_mql_set_levels(name, spec.levels))
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);')
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append('}')
        return lines

    if obj_type == "OBJ_GANNFAN":
        if not (a1 and a2):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        p1 = a1.price
        # MQL signature uses time2 and a dummy price; docs show 0 as last coord.
        scale = float(spec.metadata.get("scale", 1.0) or 1.0)
        direction = "true" if bool(spec.metadata.get("direction_descending", False)) else "false"
        color = str(spec.metadata.get("color", "clrSilver") or "clrSilver")
        lines.append(f'// {comment}')
        lines.append(f'ObjectDelete(chartId, "{name}");')
        lines.append(f'if(!ObjectCreate(chartId, "{name}", OBJ_GANNFAN, 0, {t1}, {p1}, {t2}, 0))')
        lines.append('{ Print("✗ create OBJ_GANNFAN failed: ", GetLastError()); }')
        lines.append('else {')
        lines.append(f'ObjectSetDouble(chartId, "{name}", OBJPROP_SCALE, {scale});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_DIRECTION, {direction});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);')
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append('}')
        return lines

    if obj_type == "OBJ_GANNGRID":
        if not (a1 and a2):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        p1 = a1.price
        scale = float(spec.metadata.get("scale", 1.0) or 1.0)
        direction = "true" if bool(spec.metadata.get("direction_descending", False)) else "false"
        color = str(spec.metadata.get("color", "clrSilver") or "clrSilver")
        lines.append(f'// {comment}')
        lines.append(f'ObjectDelete(chartId, "{name}");')
        lines.append(f'if(!ObjectCreate(chartId, "{name}", OBJ_GANNGRID, 0, {t1}, {p1}, {t2}, 0))')
        lines.append('{ Print("✗ create OBJ_GANNGRID failed: ", GetLastError()); }')
        lines.append('else {')
        lines.append(f'ObjectSetDouble(chartId, "{name}", OBJPROP_SCALE, {scale});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_DIRECTION, {direction});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});')
        lines.append(f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);')
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append('}')
        return lines

    # generic overlays produced by our engine (rectangle/text/arrow/hline)
    if obj_type in ("OBJ_RECTANGLE", "OBJ_TEXT", "OBJ_ARROW", "OBJ_HLINE"):
        return _generic_object_lines(name, spec, description, tooltip)

    # Unknown types are ignored for safety
    return []


def _mql_set_levels(obj_name: str, levels: list[ObjectLevel]) -> list[str]:
    if not levels:
        return []
    lines: list[str] = []
    lines.append(f'ObjectSetInteger(chartId, "{obj_name}", OBJPROP_LEVELS, {len(levels)});')
    for i, lv in enumerate(levels):
        lines.append(f'ObjectSetDouble(chartId, "{obj_name}", OBJPROP_LEVELVALUE, {i}, {float(lv.value)});')
        if lv.color:
            lines.append(f'ObjectSetInteger(chartId, "{obj_name}", OBJPROP_LEVELCOLOR, {i}, {lv.color});')
        if lv.style:
            lines.append(f'ObjectSetInteger(chartId, "{obj_name}", OBJPROP_LEVELSTYLE, {i}, {lv.style});')
        if lv.width:
            lines.append(f'ObjectSetInteger(chartId, "{obj_name}", OBJPROP_LEVELWIDTH, {i}, {int(lv.width)});')
        if lv.text:
            lines.append(f'ObjectSetString(chartId, "{obj_name}", OBJPROP_LEVELTEXT, {i}, "{_mql_str(lv.text)}");')
    return lines


def _generic_object_lines(name: str, spec: MT5ObjectSpec, description: str, tooltip: str) -> list[str]:
    a1 = spec.anchor_1
    a2 = spec.anchor_2
    if spec.object_type == "OBJ_HLINE":
        if not a1:
            return []
        p = float(a1.price)
        color = str(spec.metadata.get("color", "clrSilver") or "clrSilver")
        width = int(spec.metadata.get("width", 1) or 1)
        lines = [
            f'// {_mql_str(description)}',
            f'ObjectDelete(chartId, "{name}");',
            f'if(!ObjectCreate(chartId, "{name}", OBJ_HLINE, 0, 0, {p})) {{ Print("✗ create OBJ_HLINE failed: ", GetLastError()); }}',
            "else {",
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_WIDTH, {width});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);',
        ]
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append("}")
        return lines

    if spec.object_type == "OBJ_TEXT":
        if not a1:
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        p1 = a1.price
        text = _mql_str(str(spec.metadata.get("text", spec.context.label or spec.object_type)))
        color = str(spec.metadata.get("color", "clrSilver") or "clrSilver")
        font_size = int(spec.metadata.get("font_size", 9) or 9)
        lines = [
            f'// {_mql_str(description)}',
            f'ObjectDelete(chartId, "{name}");',
            f'if(!ObjectCreate(chartId, "{name}", OBJ_TEXT, 0, {t1}, {p1})) {{ Print("✗ create OBJ_TEXT failed: ", GetLastError()); }}',
            "else {",
            f'ObjectSetString(chartId, "{name}", OBJPROP_TEXT, "{text}");',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_FONTSIZE, {font_size});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_BACK, false);',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_HIDDEN, false);',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);',
        ]
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip, set_text=False))
        lines.append("}")
        return lines

    if spec.object_type == "OBJ_ARROW":
        if not a1:
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        p1 = a1.price
        color = str(spec.metadata.get("color", "clrSilver") or "clrSilver")
        arrow_code = int(spec.metadata.get("arrow_code", 233) or 233)
        lines = [
            f'// {_mql_str(description)}',
            f'ObjectDelete(chartId, "{name}");',
            f'if(!ObjectCreate(chartId, "{name}", OBJ_ARROW, 0, {t1}, {p1})) {{ Print("✗ create OBJ_ARROW failed: ", GetLastError()); }}',
            "else {",
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_ARROWCODE, {arrow_code});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);',
        ]
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append("}")
        return lines

    if spec.object_type == "OBJ_RECTANGLE":
        if not (a1 and a2):
            return []
        t1 = _mql_datetime_iso_to_string_to_time_expr(a1.time_utc)
        t2 = _mql_datetime_iso_to_string_to_time_expr(a2.time_utc)
        top = float(max(a1.price, a2.price))
        bot = float(min(a1.price, a2.price))
        color = str(spec.metadata.get("color", "clrLightSkyBlue") or "clrLightSkyBlue")
        back = "true" if bool(spec.metadata.get("back", True)) else "false"
        lines = [
            f'// {_mql_str(description)}',
            f'ObjectDelete(chartId, "{name}");',
            f'if(!ObjectCreate(chartId, "{name}", OBJ_RECTANGLE, 0, {t1}, {top}, {t2}, {bot})) {{ Print("✗ create OBJ_RECTANGLE failed: ", GetLastError()); }}',
            "else {",
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_COLOR, {color});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_FILL, true);',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_BACK, {back});',
            f'ObjectSetInteger(chartId, "{name}", OBJPROP_SELECTABLE, true);',
        ]
        lines.extend(_mql_description_tooltip_lines(name, description=description, tooltip=tooltip))
        lines.append("}")
        return lines

    return []
