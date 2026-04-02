from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import math

def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def resolve_active_model_dir(model_dir_or_root: str | Path) -> Path:
    """Resolve a model artifacts directory from either:

    1) An artifacts dir that directly contains model.pt
    2) A model root dir that contains current.json with {"active_dir": "..."}
    """
    p = Path(model_dir_or_root)

    # Direct artifact directory.
    if (p / "model.pt").exists():
        return p

    # Model root with pointer file.
    pointer = p / "current.json"
    if not pointer.exists():
        raise FileNotFoundError(f"No model.pt in {p} and no current.json pointer found")

    data = _read_json(pointer)
    active = data.get("active_dir")
    if not active:
        raise ValueError(f"{pointer} missing required field: active_dir")

    active_p = Path(str(active))
    if not active_p.is_absolute():
        active_p = (p / active_p).resolve()

    if not (active_p / "model.pt").exists():
        raise FileNotFoundError(active_p / "model.pt")

    return active_p


def write_current_pointer(
    model_root: str | Path,
    *,
    active_dir: str | Path,
    metrics: Optional[dict[str, Any]] = None,
    trained_at: Optional[str] = None,
) -> Path:
    """Write outputs/models/asia_sweep_mss/current.json (atomic).

    Stores at minimum:
      - active_dir
      - trained_at (UTC ISO)
    """
    root = Path(model_root)
    act = Path(active_dir)

    # Prefer a relative path when the active dir is inside the root folder.
    try:
        active_value: str
        act_resolved = act.resolve()
        root_resolved = root.resolve()
        if str(act_resolved).lower().startswith(str(root_resolved).lower() + os.sep.lower()):
            active_value = str(act_resolved.relative_to(root_resolved))
        else:
            active_value = str(act_resolved)
    except Exception:
        active_value = str(act)

    if not trained_at:
        trained_at = datetime.now(timezone.utc).isoformat()

    obj: dict[str, Any] = {
        "active_dir": active_value,
        "trained_at": str(trained_at),
    }
    if isinstance(metrics, dict):
        # Copy a few useful fields if present (best-effort).
        for k in ("best_val_auc", "test_auc", "test_acc", "best_epoch"):
            if k in metrics:
                v = metrics.get(k)
                # Keep pointer JSON strict: avoid NaN/inf and non-primitive types.
                if isinstance(v, bool):
                    obj[k] = bool(v)
                elif isinstance(v, int):
                    obj[k] = int(v)
                elif isinstance(v, float):
                    if math.isfinite(v):
                        obj[k] = float(v)
                elif v is None:
                    # omit None fields rather than writing null into current.json
                    pass

    path = root / "current.json"
    _atomic_write_json(path, obj)
    return path
