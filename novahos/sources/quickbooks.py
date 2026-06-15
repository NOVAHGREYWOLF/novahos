"""QuickBooks Online — read-only accounting (invoices/P&L). (Sources.)

Pulls the business books (invoices to start). OAuth token comes from NovaHub ConnectedIdentity
over the mesh (provider `quickbooks`) — so it lights up once that provider is configured in the
hub; until then `identity()` returns None and this yields no items (graceful). The company
`realm_id` lives in the connector `meta` (or the identity payload). Read-only — never writes.
"""
from __future__ import annotations

import os

import httpx

from ._identity import identity
from .base import RawItem, SourceBackend
from .registry import register


@register
class QuickBooksSource(SourceBackend):
    source = "quickbooks"
    mode = "official-api"
    capabilities = {"pull"}
    privacy_floor = "private"

    async def pull(self, user_email: str, since: str | None = None) -> list[RawItem]:
        ident = await identity(user_email, "quickbooks")
        token = (ident or {}).get("access_token")
        realm = self.cfg.get("realm_id") or (ident or {}).get("realm_id")
        if not (token and realm):
            return []  # provider not configured / not connected → no items (graceful)

        base = (os.environ.get("QBO_API_BASE") or "https://quickbooks.api.intuit.com").rstrip("/")
        items: list[RawItem] = []
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.get(
                    f"{base}/v3/company/{realm}/query",
                    params={"query": "select * from Invoice maxresults 50"},
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
                if r.status_code != 200:
                    return []
                invoices = (r.json() or {}).get("QueryResponse", {}).get("Invoice", [])
            for inv in invoices:
                items.append(RawItem(
                    source="quickbooks", type="financial",
                    title=f"Invoice {inv.get('DocNumber')} ${inv.get('TotalAmt')}",
                    content=f"Invoice {inv.get('DocNumber')} · total {inv.get('TotalAmt')} · "
                            f"balance {inv.get('Balance')} · due {inv.get('DueDate')}",
                    dedup_key=f"qbo-inv-{inv.get('Id')}", ts=inv.get("TxnDate"), domain="business",
                    meta={"total": inv.get("TotalAmt"), "balance": inv.get("Balance")},
                ))
        except Exception:
            return items
        return items
