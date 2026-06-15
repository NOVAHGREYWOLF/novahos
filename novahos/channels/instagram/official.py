"""Instagram · official mode — Meta Graph API only. Default. Zero ban risk. (Channels; extras.)

Publishing via the documented media-container flow (create → poll FINISHED → publish). Reels/
stories need a public video URL. Comment replies + 24h-window DMs + insights supported;
likes/follows/cold DMs are NOT. Without credentials every call returns `dry_run`.
"""
from __future__ import annotations

import asyncio
import os

import httpx

from ..base import AccountRef, ChannelBackend, InsightRow, MediaRef, PublishResult

_INSIGHT_METRICS = "reach,impressions,likes,comments,saved,shares,plays,profile_visits,follows,link_clicks"


def _graph_version() -> str:
    return os.environ.get("META_GRAPH_VERSION", "v21.0")


class InstagramOfficial(ChannelBackend):
    channel = "instagram"
    mode = "official"
    risk_floor = 0
    capabilities = {
        "publish_reel", "publish_post", "publish_story", "schedule_post",
        "reply_comment", "send_dm", "read_insights",
    }

    def __init__(self) -> None:
        self.base = f"https://graph.facebook.com/{_graph_version()}"

    @staticmethod
    def _token(account: AccountRef) -> str | None:
        return (account.auth or {}).get("access_token")

    def _live(self, account: AccountRef) -> bool:
        return bool(account.ig_user_id and self._token(account))

    async def _create_container(self, client, account, media, body, kind) -> str:
        params = {"caption": body, "access_token": self._token(account)}
        if kind == "reel":
            params |= {"media_type": "REELS", "video_url": media.url}
        elif kind == "story":
            params |= {"media_type": "STORIES", "video_url": media.url}
        else:
            params |= {"image_url": media.url}
        r = await client.post(f"{self.base}/{account.ig_user_id}/media", data=params)
        r.raise_for_status()
        return r.json()["id"]

    async def _await_finished(self, client, container_id, token, tries=20, delay=3.0) -> None:
        for _ in range(tries):
            r = await client.get(f"{self.base}/{container_id}",
                                 params={"fields": "status_code", "access_token": token})
            r.raise_for_status()
            if r.json().get("status_code") == "FINISHED":
                return
            await asyncio.sleep(delay)
        raise TimeoutError(f"container {container_id} not FINISHED in time")

    async def publish(self, account, media, body, kind="post", cover=None) -> PublishResult:
        if not self._live(account):
            return PublishResult(status="dry_run", warnings=["no Graph API credentials — dry run"],
                                 raw={"kind": kind, "body": body})
        if not media.url:
            return PublishResult(status="failed",
                                 warnings=["official mode needs a public media URL (set media.url)"])
        async with httpx.AsyncClient(timeout=60) as client:
            cid = await self._create_container(client, account, media, body, kind)
            await self._await_finished(client, cid, self._token(account))
            res = await client.post(f"{self.base}/{account.ig_user_id}/media_publish",
                                    data={"creation_id": cid, "access_token": self._token(account)})
            res.raise_for_status()
            data = res.json()
            pid, permalink = data.get("id"), None
            if pid:
                pr = await client.get(f"{self.base}/{pid}",
                                      params={"fields": "permalink", "access_token": self._token(account)})
                if pr.is_success:
                    permalink = pr.json().get("permalink")
            return PublishResult(status="published", platform_post_id=pid, permalink=permalink, raw=data)

    async def schedule(self, account, media, body, run_at, kind="post") -> PublishResult:
        return PublishResult(status="scheduled", raw={"run_at": str(run_at), "kind": kind})

    async def reply_comment(self, account, comment_id, text) -> PublishResult:
        if not self._live(account):
            return PublishResult(status="dry_run", warnings=["no credentials — dry run"])
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base}/{comment_id}/replies",
                                  data={"message": text, "access_token": self._token(account)})
            r.raise_for_status()
            return PublishResult(status="published", raw=r.json())

    async def send_dm_24h(self, account, recipient_id, text) -> PublishResult:
        if not self._live(account):
            return PublishResult(status="dry_run", warnings=["no credentials — dry run"])
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base}/{account.ig_user_id}/messages",
                json={"recipient": {"id": recipient_id}, "message": {"text": text}},
                params={"access_token": self._token(account)},
            )
            r.raise_for_status()
            return PublishResult(status="published", raw=r.json())

    async def read_insights(self, account, post_ids) -> list[InsightRow]:
        if not self._live(account):
            return [InsightRow(platform_post_id=pid, raw={"dry_run": True}) for pid in post_ids]
        out: list[InsightRow] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for pid in post_ids:
                r = await client.get(f"{self.base}/{pid}/insights",
                                     params={"metric": _INSIGHT_METRICS, "access_token": self._token(account)})
                if not r.is_success:
                    out.append(InsightRow(platform_post_id=pid, raw={"error": r.text}))
                    continue
                vals = {d["name"]: (d.get("values", [{}])[0].get("value", 0)) for d in r.json().get("data", [])}
                out.append(InsightRow(
                    platform_post_id=pid,
                    reach=vals.get("reach", 0), impressions=vals.get("impressions", 0),
                    likes=vals.get("likes", 0), comments=vals.get("comments", 0),
                    saves=vals.get("saved", 0), shares=vals.get("shares", 0),
                    plays=vals.get("plays", 0), profile_visits=vals.get("profile_visits", 0),
                    follows=vals.get("follows", 0), link_clicks=vals.get("link_clicks", 0), raw=vals,
                ))
        return out
