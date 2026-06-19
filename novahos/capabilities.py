"""NovahOS capability manifest — what every app can pull from the platform. (Foundation; stdlib.)

So an app builds ON shared capability instead of rebuilding it. The placement rule: if a second
app could ever use a thing, it lives here in `novahos`, and shows up in this manifest. Import-light:
the source/agent/channel registries are read lazily and degrade to empty if their extras aren't
installed.
"""
from __future__ import annotations


def capabilities() -> dict:
    out: dict = {
        "kernel": ["constitution", "consent", "privacy", "warden", "validators", "mcp", "context"],
        "rails": ["service_auth", "service_client", "knowledge"],
        "sources": [],
        "agents": {},
        "channels": [],
    }
    try:
        from .sources.registry import all_sources
        out["sources"] = sorted(all_sources().keys())
    except Exception:
        pass
    try:
        from .agents import REGISTRY as A
        out["agents"] = {k: sorted(v.keys()) for k, v in A.items()}
    except Exception:
        pass
    try:
        from .channels.registry import _REGISTRY as C
        out["channels"] = sorted(C.keys())
    except Exception:
        pass
    return out
