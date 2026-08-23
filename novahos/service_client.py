"""Service-to-service client — the CONSUMER half of the two-way mesh. (Rails; stdlib.)

How one app calls another's token-authed API. Base URLs from per-app env vars, so deploys
stay decoupled. Stdlib only (urllib).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .service_auth import TOKEN_ENV, TOKEN_HEADER

APP_URL_ENV = {
    "novahawk": "NOVAHAWK_API_URL",
    "icp": "ICP_API_URL",
    "campaign": "CAMPAIGN_API_URL",
    "hub": "HUB_API_URL",
}


class ServiceError(Exception):
    """Raised when a cross-app call can't be made or returns an error status."""


def _mesh_token(target_app: str, token_env: str) -> str:
    """The token this service PRESENTS on an outbound mesh call — per-spoke aware,
    so kernel-mediated calls keep working after the legacy shared token is retired.

    Resolution order:
      1. token_env (the explicit per-call env, default LEADFUEL_SERVICE_TOKEN) when
         set — byte-identical to the legacy behavior whenever that env exists.
      2. Calling the HUB → this service's OWN per-spoke token. A spoke's env holds
         exactly its own SERVICE_TOKEN_<SELF> plus SERVICE_TOKEN_HUB (kept to
         RECOGNISE the hub inbound), so excluding HUB leaves precisely the self
         token — and the hub attributes the call to the right spoke.
      3. Calling a SPOKE → SERVICE_TOKEN_HUB. Post-migration every spoke recognises
         the hub's token (it is the one non-self token in every spoke's env), so it
         is the universally-accepted outbound credential for hub→spoke and
         spoke→spoke calls alike.
    Returns "" when nothing is configured (caller raises with a helpful message)."""
    tok = (os.environ.get(token_env) or "").strip()
    if tok:
        return tok
    if target_app == "hub":
        own = {k: (v or "").strip() for k, v in os.environ.items()
               if k.startswith("SERVICE_TOKEN_") and (v or "").strip()
               and k != "SERVICE_TOKEN_HUB"}
        if len(own) == 1:
            return next(iter(own.values()))
        # Ambiguous (e.g. running ON the hub, which holds every spoke's token):
        # fall through to the hub's own token so the call still authenticates.
    return (os.environ.get("SERVICE_TOKEN_HUB") or "").strip()


def base_url(app: str) -> str:
    env = APP_URL_ENV.get(app)
    if not env:
        raise ServiceError(f"unknown app '{app}' (known: {', '.join(APP_URL_ENV)})")
    return (os.environ.get(env) or "").rstrip("/")


def call(app: str, path: str, *, method: str = "GET", params: dict | None = None,
         body: dict | None = None, token_env: str = TOKEN_ENV, timeout: int = 20) -> dict:
    base = base_url(app)
    if not base:
        raise ServiceError(f"{app} API URL not configured ({APP_URL_ENV[app]})")
    token = _mesh_token(app, token_env)
    if not token:
        raise ServiceError(
            f"no service token configured ({token_env}, SERVICE_TOKEN_<SELF> or SERVICE_TOKEN_HUB)")

    url = base + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    headers = {TOKEN_HEADER: token, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise ServiceError(f"{app} {path} → HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise ServiceError(f"{app} {path} unreachable: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ServiceError(f"{app} {path} returned non-JSON") from e


# ── convenience wrappers (the named edges of the mesh) ───────────────────────
def get_leads(email: str, *, lens=None, priority=None, limit: int = 200) -> dict:
    return call("novahawk", "/api/leads",
                params={"email": email, "lens": lens, "priority": priority, "limit": limit})


def get_icp(email: str) -> dict:
    return call("icp", f"/api/icp/{urllib.parse.quote(email)}")


def import_campaign_leads(campaign_id, leads: list[dict]) -> dict:
    return call("campaign", "/api/campaigns/import",
                method="POST", body={"campaign_id": campaign_id, "leads": leads})
