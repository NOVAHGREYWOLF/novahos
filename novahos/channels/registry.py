"""Resolve a ChannelBackend from an AgentContext (or account). (Channels.)

PUBLISHER and the pipeline call resolve(ctx) and get a ready backend — never importing a concrete
class. For Instagram the compliance_mode picks official/assisted/autonomous; other channels have a
single backend. Adding a channel = register it here; agents don't change.
"""
from __future__ import annotations

from .base import AccountRef, ChannelBackend
from .instagram.assisted import InstagramAssisted
from .instagram.autonomous import InstagramAutonomous
from .instagram.official import InstagramOfficial
from .linkedin import LinkedInBackend
from .twitter import TwitterBackend

_REGISTRY: dict[str, dict[str, type[ChannelBackend]]] = {
    "instagram": {
        "official": InstagramOfficial,
        "assisted": InstagramAssisted,
        "autonomous": InstagramAutonomous,
    },
    "linkedin": {"_": LinkedInBackend},
    "twitter": {"_": TwitterBackend},
}
_CACHE: dict[tuple[str, str], ChannelBackend] = {}


def _resolve(channel: str, mode: str) -> ChannelBackend:
    modes = _REGISTRY.get(channel) or {"_": InstagramOfficial}
    cls = modes.get(mode) or modes.get("_") or next(iter(modes.values()))
    key = (channel, cls.__name__)
    if key not in _CACHE:
        _CACHE[key] = cls()
    return _CACHE[key]


def resolve(ctx_or_account) -> ChannelBackend:
    channel = getattr(ctx_or_account, "channel", None) or "instagram"
    mode = getattr(ctx_or_account, "compliance_mode", None) or "official"
    return _resolve(channel, mode)


def account_ref(account, channel: str | None = None) -> AccountRef:
    return AccountRef(
        id=account.id, handle=account.handle,
        channel=channel or getattr(account, "channel", "instagram"),
        ig_user_id=getattr(account, "ig_user_id", None),
        compliance_mode=getattr(account, "compliance_mode", "official"),
        auth=getattr(account, "auth", {}) or {},
    )
