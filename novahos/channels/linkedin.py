"""LinkedIn channel — official API publish + insights. Transport-only. (Channels; extras.)

The kernel backend is transport-only: given an access token + author URN on `account.auth`, it
posts via the UGC API and reads engagement via socialActions. OAuth, token storage/refresh,
encryption, and any hub-proxy routing live in the consuming APP (e.g. NovaHound), which builds the
AccountRef.auth and calls here. Without a token it returns `dry_run`, so it's safe to exercise.

    account.auth = {"access_token": "...", "author_urn": "urn:li:person:..."}
"""
from __future__ import annotations

import urllib.parse

import httpx

from .base import AccountRef, ChannelBackend, InsightRow, MediaRef, PublishResult

UGC_URL = "https://api.linkedin.com/v2/ugcPosts"
SOCIAL_ACTIONS_URL = "https://api.linkedin.com/v2/socialActions"


class LinkedInBackend(ChannelBackend):
    channel = "linkedin"
    mode = "official"
    risk_floor = 0
    capabilities = {"publish_post", "schedule_post", "read_insights"}

    @staticmethod
    def _token(account: AccountRef) -> str | None:
        return (account.auth or {}).get("access_token")

    @staticmethod
    def _author(account: AccountRef) -> str | None:
        return (account.auth or {}).get("author_urn")

    async def publish(self, account: AccountRef, media: MediaRef, body: str,
                      kind: str = "post", cover: MediaRef | None = None) -> PublishResult:
        token, author = self._token(account), self._author(account)
        if not token or not author:
            return PublishResult(status="dry_run", warnings=["no LinkedIn token/author — dry run"],
                                 raw={"body": body})
        share: dict = {"shareCommentary": {"text": body}, "shareMediaCategory": "NONE"}
        if media and media.url:
            share["shareMediaCategory"] = "ARTICLE"
            share["media"] = [{"status": "READY", "originalUrl": media.url}]
        payload = {
            "author": author, "lifecycleState": "PUBLISHED",
            "specificContent": {"com.linkedin.ugc.ShareContent": share},
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(UGC_URL, json=payload, headers={
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            })
            if r.status_code >= 300:
                return PublishResult(status="failed", warnings=[f"LinkedIn API {r.status_code}: {r.text[:300]}"])
            urn = r.headers.get("x-restli-id") or (r.json().get("id", "") if r.content else "")
            permalink = f"https://www.linkedin.com/feed/update/{urn}" if urn else None
            return PublishResult(status="published", platform_post_id=urn, permalink=permalink)

    async def schedule(self, account: AccountRef, media: MediaRef, body: str,
                       run_at, kind: str = "post") -> PublishResult:
        # No native future-publish; the app's scheduler fires publish() at run_at.
        return PublishResult(status="scheduled", raw={"run_at": str(run_at)})

    async def read_insights(self, account: AccountRef, post_ids: list[str]) -> list[InsightRow]:
        token = self._token(account)
        if not token:
            return [InsightRow(platform_post_id=p, raw={"dry_run": True}) for p in post_ids]
        out: list[InsightRow] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for urn in post_ids:
                enc = urllib.parse.quote(urn, safe="")
                r = await client.get(f"{SOCIAL_ACTIONS_URL}/{enc}",
                                     headers={"Authorization": f"Bearer {token}",
                                              "X-Restli-Protocol-Version": "2.0.0"})
                if r.status_code != 200:
                    out.append(InsightRow(platform_post_id=urn, raw={"error": r.text[:200]}))
                    continue
                d = r.json()
                likes = ((d.get("likesSummary") or {}).get("totalLikes")
                         or (d.get("reactionsSummary") or {}).get("totalReactions") or 0)
                comments = (d.get("commentsSummary") or {}).get("totalFirstLevelComments") or 0
                out.append(InsightRow(platform_post_id=urn, likes=int(likes or 0),
                                      comments=int(comments or 0), raw=d))
        return out
