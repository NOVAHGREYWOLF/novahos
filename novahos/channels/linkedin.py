"""LinkedIn channel — stub proving the same agents/registry serve another channel. (Channels.)

When implemented, posts via the LinkedIn UGC/Posts API. It exists now so the shared
WORDSMITH/PUBLISHER + registry already work for channel='linkedin' — only this backend needs
filling in; nothing in the agents or pipeline changes.
"""
from __future__ import annotations

from .base import AccountRef, ChannelBackend, InsightRow, MediaRef, PublishResult


class LinkedInBackend(ChannelBackend):
    channel = "linkedin"
    mode = "official"
    risk_floor = 0
    capabilities = {"publish_post", "schedule_post", "read_insights"}

    async def publish(self, account: AccountRef, media: MediaRef, body: str,
                      kind: str = "post", cover: MediaRef | None = None) -> PublishResult:
        return PublishResult(status="dry_run", warnings=["LinkedIn backend not yet implemented (stub)"],
                             raw={"kind": kind, "body": body})

    async def schedule(self, account, media, body, run_at, kind="post") -> PublishResult:
        return PublishResult(status="scheduled", raw={"run_at": str(run_at)})

    async def read_insights(self, account, post_ids) -> list[InsightRow]:
        return [InsightRow(platform_post_id=pid, raw={"stub": True}) for pid in post_ids]
