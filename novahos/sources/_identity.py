"""Fetch a user's OAuth identity (incl. access_token) from NovaHub over the mesh. (Sources.)

Reuses ConnectedIdentity in the hub so token-based sources need NO new login. Fail-quiet:
returns None if the mesh token is unset, the hub is unreachable, or the provider isn't
configured yet — the source then yields no items (graceful, not an error).
"""
from __future__ import annotations

import os

import httpx

TOKEN_ENV = "LEADFUEL_SERVICE_TOKEN"


def _hub() -> str:
    return (os.environ.get("HUB_API_URL") or os.environ.get("NOVAHUB_URL")
            or "https://leadfuel.cloud").rstrip("/")


async def identity(user_email: str, provider: str) -> dict | None:
    tok = (os.environ.get(TOKEN_ENV) or "").strip()
    if not (tok and user_email):
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"{_hub()}/api/identity/{provider}",
                            params={"email": user_email}, headers={"X-Service-Token": tok})
        b = r.json() if r.status_code == 200 else {}
        return b if b.get("ok") else None
    except Exception:
        return None
