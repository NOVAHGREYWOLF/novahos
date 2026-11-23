#!/usr/bin/env python3
"""Merge the session-budget kit's .claude/settings.json into another repo's, never overwriting.

    python3 scripts/merge_claude_settings.py SOURCE_SETTINGS TARGET_SETTINGS

Adds, and only adds: hook entries whose command the target does not already run, `permissions.allow`
entries it lacks, and `env` keys it has not set. Every other key (and any value the target already chose)
is left exactly as found. Writes only when something changed, so a rerun is a no-op. Exits 1 and writes
nothing if the target is not a JSON object or a section has an unexpected shape.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


def _commands(entry: dict) -> set[str]:
    return {h.get("command") for h in entry.get("hooks", []) if isinstance(h, dict) and h.get("command")}


def _section(parent: dict, key: str, kind: type):
    value = parent.setdefault(key, kind())
    if not isinstance(value, kind):
        raise ValueError(f"target '{key}' is not a {kind.__name__}")
    return value


def merge(src: dict, dst: dict) -> dict:
    """Fold src's hooks / permissions.allow / env into dst. Mutates and returns dst."""
    for event, entries in (src.get("hooks") or {}).items():
        have = _section(_section(dst, "hooks", dict), event, list)
        running = set().union(*(_commands(e) for e in have if isinstance(e, dict)))
        for entry in entries:
            if not _commands(entry) <= running:
                have.append(entry)
                running |= _commands(entry)
    for rule in (src.get("permissions") or {}).get("allow") or []:
        allow = _section(_section(dst, "permissions", dict), "allow", list)
        if rule not in allow:
            allow.append(rule)
    for key, value in (src.get("env") or {}).items():
        _section(dst, "env", dict).setdefault(key, value)
    return dst


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    src_path, dst_path = Path(argv[1]), Path(argv[2])
    try:
        src = json.loads(src_path.read_text())
        dst = json.loads(dst_path.read_text()) if dst_path.exists() else {}
        if not isinstance(dst, dict):
            raise ValueError("target is not a JSON object")
        merged = merge(src, copy.deepcopy(dst))
    except (OSError, ValueError) as e:
        print(f"{dst_path}: {e}", file=sys.stderr)
        return 1
    if merged == dst and dst_path.exists():
        print("unchanged")
        return 0
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(json.dumps(merged, indent=2) + "\n")
    print("merged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
