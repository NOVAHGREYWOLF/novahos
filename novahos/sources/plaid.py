"""Plaid — read-only bank transactions + balances. (Sources.)

Banking aggregator across ~12k institutions. **Read-only**: this pulls transactions; it NEVER
moves money (money is hands-off — any write path must go through WARDEN at RED). The per-user
Plaid `access_token` (obtained via Plaid Link, exchanged + stored encrypted by the app) lives in
the connector `meta`; client creds come from env (`PLAID_CLIENT_ID`/`PLAID_SECRET`/`PLAID_HOST`),
so this works Lucid-direct with no NovaHub change. Pulled items are typed `financial` → the
privacy classifier marks them PRIVATE (local-only, never to third parties).
"""
from __future__ import annotations

import os

import httpx

from .base import RawItem, SourceBackend
from .registry import register


@register
class PlaidSource(SourceBackend):
    source = "plaid"
    mode = "official-api"
    capabilities = {"pull"}
    privacy_floor = "private"

    async def pull(self, user_email: str, since: str | None = None) -> list[RawItem]:
        token = self.cfg.get("access_token")
        cid, secret = os.environ.get("PLAID_CLIENT_ID"), os.environ.get("PLAID_SECRET")
        host = (os.environ.get("PLAID_HOST") or "https://sandbox.plaid.com").rstrip("/")
        if not (token and cid and secret):
            return []  # not configured → no items (graceful)

        items: list[RawItem] = []
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                # /transactions/sync is incremental: `since` carries Plaid's next_cursor.
                r = await c.post(f"{host}/transactions/sync", json={
                    "client_id": cid, "secret": secret, "access_token": token,
                    "cursor": since or "", "count": 250,
                })
                if r.status_code != 200:
                    return []
                data = r.json() or {}
            cursor = data.get("next_cursor")
            for t in data.get("added", []):
                name = t.get("name") or t.get("merchant_name") or "transaction"
                amt = t.get("amount")
                cats = ", ".join(t.get("category") or [])
                items.append(RawItem(
                    source="plaid", type="financial",
                    title=f"{name} ${amt}",
                    content=f"{t.get('date')} · {name} · amount {amt} "
                            f"{t.get('iso_currency_code') or ''} · [{cats}]",
                    dedup_key=t.get("transaction_id"), ts=t.get("date"), domain="personal",
                    meta={"amount": amt, "account_id": t.get("account_id"),
                          "category": t.get("category"), "next_cursor": cursor},
                ))
        except Exception:
            return items
        return items
