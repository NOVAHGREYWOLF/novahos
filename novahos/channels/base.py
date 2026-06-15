"""ChannelBackend — the abstraction that lets PUBLISHER post anywhere. (Channels; extras.)

One interface, many channels (instagram, linkedin, email…). Within a channel there may be
sub-modes (Instagram's official/assisted/autonomous tiers). PUBLISHER never imports a concrete
backend — it asks the registry to resolve one from the AgentContext.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any


class NotSupported(RuntimeError):
    """Raised when an action isn't available on the active channel/mode."""


@dataclass
class AccountRef:
    id: str
    handle: str
    channel: str = "instagram"
    ig_user_id: str | None = None
    compliance_mode: str = "official"
    auth: dict = field(default_factory=dict)


@dataclass
class MediaRef:
    kind: str
    path: str | None = None
    url: str | None = None
    duration_s: float | None = None


@dataclass
class PublishResult:
    status: str
    platform_post_id: str | None = None
    permalink: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class InsightRow:
    platform_post_id: str
    reach: int = 0
    impressions: int = 0
    likes: int = 0
    comments: int = 0
    saves: int = 0
    shares: int = 0
    plays: int = 0
    profile_visits: int = 0
    follows: int = 0
    link_clicks: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class ChannelBackend(ABC):
    channel: str = "base"
    mode: str = "base"
    capabilities: set[str] = set()
    risk_floor: int = 0

    def supports(self, action_type: str) -> bool:
        return action_type in self.capabilities

    def _require(self, action_type: str) -> None:
        if not self.supports(action_type):
            raise NotSupported(f"{action_type} not supported on {self.channel}/{self.mode}")

    async def publish(self, account: AccountRef, media: MediaRef, body: str,
                      kind: str = "post", cover: MediaRef | None = None) -> PublishResult:
        self._require(f"publish_{kind}"); raise NotImplementedError

    async def schedule(self, account: AccountRef, media: MediaRef, body: str,
                       run_at, kind: str = "post") -> PublishResult:
        self._require("schedule_post"); raise NotImplementedError

    async def reply_comment(self, account: AccountRef, comment_id: str, text: str) -> PublishResult:
        self._require("reply_comment"); raise NotImplementedError

    async def send_dm_24h(self, account: AccountRef, recipient_id: str, text: str) -> PublishResult:
        self._require("send_dm"); raise NotImplementedError

    async def read_insights(self, account: AccountRef, post_ids: list[str]) -> list[InsightRow]:
        self._require("read_insights"); raise NotImplementedError

    async def like(self, account: AccountRef, target_id: str) -> PublishResult:
        self._require("engage"); raise NotImplementedError

    async def follow(self, account: AccountRef, target_id: str) -> PublishResult:
        self._require("engage"); raise NotImplementedError

    async def cold_dm(self, account: AccountRef, recipient_id: str, text: str) -> PublishResult:
        self._require("cold_dm"); raise NotImplementedError
