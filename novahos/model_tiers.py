"""One place for model IDs: apps ask for a TIER, the kernel says which model that is.

WHY THIS FILE EXISTS
────────────────────
On 2026-09-27 five apps were found naming six different model IDs between them:

    reach     claude-sonnet-4-5
    signal    claude-sonnet-4-6
    scope     claude-sonnet-4-5 and claude-haiku-4-5
    odyssey   claude-haiku-3-5     <- not a valid ID; Haiku 3.5 was `claude-3-5-haiku-*`,
                                      and that model retired on 2026-02-19
    lucid     claude-opus-4-8

Each one was a reasonable choice on the day it was typed, and each one is now a separate
thing to remember when the estate moves to a newer model. The fix is to stop letting an app
name a model at all: an app says WHAT KIND of work a call is (``reason``, ``write``,
``classify``) and reads the model ID from here. Moving the estate is then a one-line change
in this file, reviewed once.

Stdlib-only on purpose, like ``gateway_url``: novahos is a library installed into every host,
and a plain ``novahos`` install (no extras) must still be able to answer "which model?".

This module does not route, gate or meter anything — that stays in ``novahos.llm``. It only
names models. ``CoreSettings.reasoning_model`` / ``cheap_model`` are left as they are for now;
pointing them at these tiers changes what the kernel's own calls run on and is its own change.
"""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

#: The tiers, and the current model each one maps to. Read-only: change it HERE, not at runtime.
#:
#:   reason    hard, multi-step work where quality matters more than cost (planning, agents,
#:             anything a person will act on without re-checking).
#:   write     everyday generation: drafting, summarising, rewriting, chat.
#:   classify  short, high-volume, latency-sensitive calls: labels, routing, yes/no, extraction.
TIERS: Mapping[str, str] = MappingProxyType({
    "reason": "claude-opus-5-5",
    "write": "claude-sonnet-5-5",
    "classify": "claude-haiku-4-5",
})

#: IDs apps were found using, and the tier each one should move to. Lets a host (or a check in
#: CI) translate what it has today into the tier it should be asking for. An ID in here is
#: NOT an endorsement of that ID — several are previous generations, and one never existed.
LEGACY_IDS: Mapping[str, str] = MappingProxyType({
    "claude-opus-4-8": "reason",
    "claude-sonnet-4-6": "write",
    "claude-sonnet-4-5": "write",
    "claude-haiku-4-5-20251001": "classify",
    "claude-haiku-3-5": "classify",          # invalid ID (odyssey)
    "claude-3-5-haiku-20241022": "classify",  # retired 2026-02-19
})


class UnknownTier(KeyError):
    """Raised for a tier name this map does not define. A typo must fail, not fall back."""


def model_for(tier: str) -> str:
    """The model ID for ``tier``. Raises :class:`UnknownTier` for anything not in :data:`TIERS`.

    There is deliberately no default tier: silently handing an unknown tier the expensive
    model, or the cheap one, is exactly the kind of drift this module exists to remove.
    """
    try:
        return TIERS[tier]
    except (KeyError, TypeError):
        raise UnknownTier(
            f"unknown model tier {tier!r}; expected one of {sorted(TIERS)}"
        ) from None


def tier_for(model_id: str) -> str | None:
    """The tier a model ID belongs to — current or legacy — or ``None`` if it is not known."""
    for tier, current in TIERS.items():
        if model_id == current:
            return tier
    return LEGACY_IDS.get(model_id)


def is_current(model_id: str) -> bool:
    """True only when ``model_id`` is exactly what some tier maps to today."""
    return model_id in TIERS.values()


__all__ = ["LEGACY_IDS", "TIERS", "UnknownTier", "is_current", "model_for", "tier_for"]
