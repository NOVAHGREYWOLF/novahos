"""Shared agent registry — how apps discover the platform's agents. (Agents.)

Each entry maps a cluster → {capability: "module:function"}. Agents pull heavy deps, so this
module stays import-light: `resolve()` imports the target lazily, on demand. Apps call
`resolve("croesus","assess")` and get a callable — they never hard-import a concrete agent.
Adding an agent capability = a line here.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

REGISTRY: dict[str, dict[str, str]] = {
    "athena": {  # strategy
        "content_angles": "novahos.agents.athena.oracle:content_angles",
        "propose_from_life_data": "novahos.agents.athena.bridge:propose_from_life_data",
    },
    "croesus": {  # finance (read-only analysis)
        "assess": "novahos.agents.croesus.advisor:assess",
    },
}


def resolve(cluster: str, capability: str) -> Callable | None:
    spec = REGISTRY.get(cluster, {}).get(capability)
    if not spec:
        return None
    mod, fn = spec.split(":")
    try:
        return getattr(import_module(mod), fn)
    except Exception:
        return None
