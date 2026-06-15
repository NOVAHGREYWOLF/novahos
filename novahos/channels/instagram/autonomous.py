"""Instagram · autonomous mode — browser automation / grey-hat. HIGH BAN RISK. (Channels.)

Does what the official API forbids (auto follow/like, cold DMs, posting without app review).
Against Instagram's ToS. Gated behind account.autonomous_optin (WARDEN refuses otherwise) with a
high risk_floor (70). Inert until Phase 5; every method warns loudly.
"""
from __future__ import annotations

from ..base import AccountRef, ChannelBackend, InsightRow, PublishResult

_DANGER = ("AUTONOMOUS MODE: browser automation violates Instagram's Terms of Service and "
           "risks a permanent ban. Not implemented until you opt in (Phase 5).")


class InstagramAutonomous(ChannelBackend):
    channel = "instagram"
    mode = "autonomous"
    risk_floor = 70
    capabilities = {
        "publish_reel", "publish_post", "publish_story", "schedule_post",
        "reply_comment", "send_dm", "read_insights", "engage", "cold_dm",
    }

    async def _stub(self, action: str) -> PublishResult:
        return PublishResult(status="failed", warnings=[_DANGER, f"{action} not yet implemented"])

    async def publish(self, account, media, body, kind="post", cover=None): return await self._stub(f"publish_{kind}")
    async def schedule(self, account, media, body, run_at, kind="post"): return await self._stub("schedule")
    async def reply_comment(self, account, comment_id, text): return await self._stub("reply_comment")
    async def send_dm_24h(self, account, recipient_id, text): return await self._stub("send_dm")
    async def like(self, account, target_id): return await self._stub("like")
    async def follow(self, account, target_id): return await self._stub("follow")
    async def cold_dm(self, account, recipient_id, text): return await self._stub("cold_dm")

    async def read_insights(self, account: AccountRef, post_ids: list[str]) -> list[InsightRow]:
        return [InsightRow(platform_post_id=pid, raw={"autonomous_stub": True}) for pid in post_ids]
