"""Playbook + lens loader framework. Config-as-data, app-supplied libraries. (Foundation-ish.)

The framework lives in the kernel; the actual YAML libraries live with each APP (an app's
playbooks are channel-specific). An app registers its directories via register_dirs(...); agents
then call resolve(key). Requires pyyaml (ships with the substrate/agents extras).
"""
from __future__ import annotations

from pathlib import Path

import yaml

_PLAYBOOK_DIRS: list[Path] = []
_LENS_DIRS: list[Path] = []
_PB_CACHE: dict[str, dict] | None = None
_LENS_CACHE: dict[str, dict] | None = None


def register_dirs(playbook_dir: str | Path, lens_dir: str | Path) -> None:
    global _PB_CACHE, _LENS_CACHE
    _PLAYBOOK_DIRS.append(Path(playbook_dir))
    _LENS_DIRS.append(Path(lens_dir))
    _PB_CACHE = _LENS_CACHE = None


def reset() -> None:
    """Clear registered dirs + cache (used by tests)."""
    global _PB_CACHE, _LENS_CACHE
    _PLAYBOOK_DIRS.clear()
    _LENS_DIRS.clear()
    _PB_CACHE = _LENS_CACHE = None


def _load(dirs: list[Path]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for d in dirs:
        for f in sorted(Path(d).glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            if "key" in data:
                out[data["key"]] = data
    return out


def all_playbooks() -> dict[str, dict]:
    global _PB_CACHE
    if _PB_CACHE is None:
        _PB_CACHE = _load(_PLAYBOOK_DIRS)
    return dict(_PB_CACHE)


def all_lenses() -> dict[str, dict]:
    global _LENS_CACHE
    if _LENS_CACHE is None:
        _LENS_CACHE = _load(_LENS_DIRS)
    return dict(_LENS_CACHE)


def get_playbook(key: str, overrides: dict | None = None) -> dict:
    base = dict(all_playbooks().get(key) or {})
    if not base:
        raise KeyError(f"unknown playbook: {key}")
    if overrides:
        base |= overrides
    return base


def get_lens(key: str, overrides: dict | None = None) -> dict:
    base = dict(all_lenses().get(key) or {})
    if overrides:
        base |= overrides
    return base


def resolve(playbook_key: str, *, playbook_override: dict | None = None,
            lens_overrides: dict[str, dict] | None = None) -> dict:
    pb = get_playbook(playbook_key, playbook_override)
    lens_overrides = lens_overrides or {}
    lenses = {k: get_lens(k, lens_overrides.get(k)) for k in pb.get("target_lens_set", [])}
    return {"playbook": pb, "lenses": lenses}
