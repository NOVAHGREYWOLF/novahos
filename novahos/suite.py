"""WolfOS life-data bridge — the ATHENA bridge's transport. Fail-quiet. (Substrate.)

CONSUMER half: pull life signals (revenue, goals, journal) from WolfOS so ATHENA can propose
content goals. If the mesh isn't available, calls return None and the system degrades to manual.
(Distinct from the rails service_client — this targets the WolfOS personal layer.)
"""
from __future__ import annotations

import os

import httpx

TOKEN_ENV = "LEADFUEL_SERVICE_TOKEN"
WOLFOS_URL_ENV = "WOLFOS_BASE_URL"


def _token() -> str:
    return (os.environ.get(TOKEN_ENV) or "").strip()


def mesh_enabled() -> bool:
    return bool(_token())


def _wolfos_get(path: str, account_email: str) -> dict | None:
    base = (os.environ.get(WOLFOS_URL_ENV) or "").strip()
    if not (base and account_email and _token()):
        return None
    try:
        r = httpx.get(f"{base.rstrip('/')}{path}",
                      headers={"X-Service-Token": _token(), "X-Leadfuel-Account": account_email},
                      timeout=8.0)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def get_revenue_state(account_email: str) -> dict | None:
    return _wolfos_get("/api/revenue/state", account_email)


def get_goals(account_email: str) -> dict | None:
    return _wolfos_get("/api/goals", account_email)


def get_journal_signals(account_email: str, since: str | None = None) -> dict | None:
    q = f"?since={since}" if since else ""
    return _wolfos_get(f"/api/journal/signals{q}", account_email)
