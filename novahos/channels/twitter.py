"""X (Twitter) channel — official v2 API publish + insights. Transport-only. (Channels; extras.)

Given an access token on `account.auth`, posts via POST /2/tweets and reads public_metrics. OAuth
2.0 + PKCE, token storage/refresh, and any hub-proxy routing live in the consuming APP, which
builds AccountRef.auth and calls here. Links go inline in `body` (X auto-unfurls). 280-char cap is
validated. No token → `dry_run`.

    account.auth = {"access_token": "..."}
"""
from __future__ import annotations

import urllib.parse

import httpx

from .base import AccountRef, ChannelBackend, InsightRow, MediaRef, PublishResult

TWEETS_URL = "https://api.twitter.com/2/tweets"
MAX_TWEET_LEN = 280


class TwitterBackend(ChannelBackend):
    channel = "twitter"
    mode = "official"
    risk_floor = 0
    capabilities = {"publish_post", "schedule_post", "read_insights"}

    @staticmethod
    def _token(account: AccountRef) -> str | None:
        return (account.auth or {}).get("access_token")

    async def publish(self, account: AccountRef, media: MediaRef, body: str,
                      kind: str = "post", cover: MediaRef | None = None) -> PublishResult:
        text = (body or "").strip()
        if not text:
            return PublishResult(status="failed", warnings=["empty tweet"])
        if len(text) > MAX_TWEET_LEN:
            return PublishResult(status="failed",
                                 warnings=[f"tweet exceeds {MAX_TWEET_LEN} chars ({len(text)})"])
        token = self._token(account)
        if not token:
            return PublishResult(status="dry_run", warnings=["no X token — dry run"], raw={"body": text})
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(TWEETS_URL, json={"text": text},
                                  headers={"Authorization": f"Bearer {token}",
                                           "Content-Type": "application/json"})
            if r.status_code >= 300:
                return PublishResult(status="failed", warnings=[f"X API {r.status_code}: {r.text[:300]}"])
            tid = (r.json().get("data") or {}).get("id", "") if r.content else ""
            permalink = f"https://x.com/i/status/{tid}" if tid else None
            return PublishResult(status="published", platform_post_id=tid, permalink=permalink)

    async def schedule(self, account: AccountRef, media: MediaRef, body: str,
                       run_at, kind: str = "post") -> PublishResult:
        return PublishResult(status="scheduled", raw={"run_at": str(run_at)})

    async def read_insights(self, account: AccountRef, post_ids: list[str]) -> list[InsightRow]:
        token = self._token(account)
        if not token:
            return [InsightRow(platform_post_id=p, raw={"dry_run": True}) for p in post_ids]
        out: list[InsightRow] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for tid in post_ids:
                r = await client.get(f"{TWEETS_URL}/{urllib.parse.quote(tid)}",
                                     params={"tweet.fields": "public_metrics"},
                                     headers={"Authorization": f"Bearer {token}"})
                if r.status_code != 200:
                    out.append(InsightRow(platform_post_id=tid, raw={"error": r.text[:200]}))
                    continue
                m = ((r.json().get("data") or {}).get("public_metrics") or {})
                out.append(InsightRow(platform_post_id=tid,
                                      likes=int(m.get("like_count") or 0),
                                      comments=int(m.get("reply_count") or 0),
                                      shares=int(m.get("retweet_count") or 0), raw=m))
        return out
