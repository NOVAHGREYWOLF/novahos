"""Shared agent registry — how apps discover the platform's agents. (Agents.)

Each entry maps a cluster → {capability: "module:function"}. Agents pull heavy deps, so this
module stays import-light: `resolve()` imports the target lazily, on demand. Apps call
`resolve("croesus","assess")` and get a callable — they never hard-import a concrete agent.
Adding an agent capability = a line here.
"""
from __future__ import annotations

from importlib import import_module
from typing import Callable

# apollo and ig SHIPPED WITHOUT REGISTRY ENTRIES, which made this module's own rule
# unfollowable. Both clusters have lived under `novahos/agents/` for months with real
# capabilities in them, and neither was listed here -- so `resolve("apollo","compose")`
# returned None, and the only app that wanted them had no way to ask.
#
# novahound did the one thing this docstring forbids, because it was the only thing left:
# `compose.py` does `from novahos.agents.apollo import curator, wordsmith` and
# `video_ingest.py` does `from novahos.agents.ig.transcriber import get_transcriber`. That is
# not novahound being careless. A registry that omits half of what it registers leaves a hard
# import as the only working path, and the hard import is what this indirection exists to
# prevent: it pins the app to a module layout, so moving a file breaks a consumer in another
# repo with no warning here.
#
# CAPABILITIES ARE NAMED FOR WHAT THEY DO, NOT FOR WHO DOES THEM. `compose`, not `wordsmith`.
# The agent is an implementation detail carried on the right-hand side, which is what lets an
# agent be renamed, split or replaced without touching a caller -- the same separation the arm
# registry draws between a key and a display name. It also means two clusters may each offer a
# `compose` without colliding, because the cluster is half the address.
#
# PURE FIRST, DB-BOUND SECOND, AND BOTH ARE REGISTERED. `compose`/`rank_drafts` take only a
# context and return data; `store_drafts`/`curate`/`publish` take a session and write. An app
# with its own persistence wants the first pair, an app on the kernel's models wants the
# second, and leaving either out sends somebody back to a hard import.
REGISTRY: dict[str, dict[str, str]] = {
    "athena": {  # strategy
        "content_angles": "novahos.agents.athena.oracle:content_angles",
        "propose_from_life_data": "novahos.agents.athena.bridge:propose_from_life_data",
    },
    "croesus": {  # finance (read-only analysis)
        "assess": "novahos.agents.croesus.advisor:assess",
    },
    "apollo": {  # content — compose, rank, record, publish
        "compose": "novahos.agents.apollo.wordsmith:compose",
        "store_drafts": "novahos.agents.apollo.wordsmith:generate",
        "rank_drafts": "novahos.agents.apollo.curator:rank_dicts",
        "curate": "novahos.agents.apollo.curator:curate",
        "assemble_body": "novahos.agents.apollo.publisher:assemble_body",
        "publish": "novahos.agents.apollo.publisher:publish",
        "capture": "novahos.agents.apollo.chronicle:capture",
    },
    "ig": {  # instagram — transcribe, prepare media, run the DM funnel, read back insights
        "transcriber": "novahos.agents.ig.transcriber:get_transcriber",
        "checksum": "novahos.agents.ig.mediasmith:checksum",
        "prepare_media": "novahos.agents.ig.mediasmith:prepare",
        "dm_on_inbound": "novahos.agents.ig.dm_funnel:on_inbound",
        "dm_on_outbound": "novahos.agents.ig.dm_funnel:on_outbound",
        "dm_window_open": "novahos.agents.ig.dm_funnel:window_open",
        "dm_expire_stale": "novahos.agents.ig.dm_funnel:expire_stale",
        "sync_post": "novahos.agents.ig.insights:sync_post",
        "sync_recent": "novahos.agents.ig.insights:sync_recent",
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
