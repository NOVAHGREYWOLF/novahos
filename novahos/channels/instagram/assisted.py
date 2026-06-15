"""Instagram · assisted mode — official API PLUS rate-limited engagement helpers. (Channels.)

Inherits all official capabilities, adds `like`. Engagement automation is a grey area: WARDEN
validators enforce hard hourly caps, risk_floor is raised (30), every helper warns.
"""
from __future__ import annotations

import httpx

from ..base import AccountRef, PublishResult
from .official import InstagramOfficial

_WARN = ("engagement automation is a grey area of Meta policy — rate-limited and "
         "use at your own risk")


class InstagramAssisted(InstagramOfficial):
    mode = "assisted"
    risk_floor = 30
    capabilities = InstagramOfficial.capabilities | {"engage"}

    async def like(self, account: AccountRef, target_id: str) -> PublishResult:
        if not self._live(account):
            return PublishResult(status="dry_run", warnings=[_WARN, "no credentials — dry run"])
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base}/{target_id}/likes",
                                  data={"access_token": self._token(account)})
            ok = r.is_success
            return PublishResult(status="published" if ok else "failed",
                                 raw=r.json() if ok else {"error": r.text}, warnings=[_WARN])

    async def follow(self, account: AccountRef, target_id: str) -> PublishResult:
        return PublishResult(status="failed",
                             warnings=[_WARN, "follow is not available via the Graph API; "
                                       "use autonomous mode (higher ban risk) if you must"])
