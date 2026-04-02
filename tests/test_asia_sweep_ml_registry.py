import json
from pathlib import Path

import pytest

from ml.asia_sweep_london_mss.model_registry import resolve_active_model_dir, write_current_pointer


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")


def _mk_artifacts(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for name in ("model.pt", "feature_stats.json", "symbol_map.json", "metrics.json"):
        _touch(dir_path / name)


def test_resolve_active_model_dir_direct_artifacts(tmp_path):
    art = tmp_path / "v1_abc"
    _mk_artifacts(art)
    got = resolve_active_model_dir(art)
    assert got.resolve() == art.resolve()


def test_resolve_active_model_dir_via_current_pointer_relative(tmp_path):
    root = tmp_path / "root"
    art = root / "v1_20260325_000000"
    _mk_artifacts(art)
    (root / "current.json").write_text(json.dumps({"active_dir": "v1_20260325_000000"}), encoding="utf-8")

    got = resolve_active_model_dir(root)
    assert got.resolve() == art.resolve()


def test_write_current_pointer_writes_relative_when_inside_root(tmp_path):
    root = tmp_path / "root"
    art = root / "v1_20260325_010101"
    _mk_artifacts(art)

    pointer = write_current_pointer(root, active_dir=art, metrics={"test_auc": 0.77}, trained_at="2026-03-25T00:00:00Z")
    assert pointer.exists()
    data = json.loads(pointer.read_text(encoding="utf-8"))
    assert data["active_dir"] == "v1_20260325_010101"
    assert data["trained_at"] == "2026-03-25T00:00:00Z"
    assert data["test_auc"] == 0.77


def test_resolve_active_model_dir_pointer_missing_model_raises(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "current.json").write_text(json.dumps({"active_dir": "missing_dir"}), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        resolve_active_model_dir(root)

