"""Service-to-service auth — the PRODUCER half of the two-way mesh. (Rails; stdlib.)

Every app validates inbound calls the same way: a shared secret in the ``X-Service-Token``
header, checked constant-time against ``LEADFUEL_SERVICE_TOKEN``. The API stays OFF until
that env is set, so nothing opens a hole by default. Framework-agnostic (any headers mapping).
"""
from __future__ import annotations

import hmac
import os

TOKEN_ENV = "LEADFUEL_SERVICE_TOKEN"
TOKEN_HEADER = "X-Service-Token"


def service_token(env: str = TOKEN_ENV) -> str:
    return (os.environ.get(env) or "").strip()


def _per_spoke_tokens() -> list[str]:
    """Every per-spoke token (SERVICE_TOKEN_*) configured in THIS service's env.
    Lets a service recognise the hub (SERVICE_TOKEN_HUB) and any sibling by its
    own token, IN ADDITION to the legacy shared LEADFUEL_SERVICE_TOKEN — the
    inbound half of the per-spoke mesh. Migration-safe: accepts MORE tokens,
    never fewer, so nothing that worked on the legacy token stops working."""
    out: list[str] = []
    for k, v in os.environ.items():
        if k.startswith("SERVICE_TOKEN_"):
            v = (v or "").strip()
            if v:
                out.append(v)
    return out


def is_enabled(env: str = TOKEN_ENV) -> bool:
    """True iff ANY service token is configured — the legacy shared token OR any
    per-spoke SERVICE_TOKEN_*. Staying enabled on per-spoke tokens is what lets the
    legacy LEADFUEL_SERVICE_TOKEN be RETIRED without 503-ing the /api surface."""
    return bool(service_token(env)) or bool(_per_spoke_tokens())


def token_matches(sent: str | None, env: str = TOKEN_ENV) -> bool:
    """Constant-time compare of a presented token against ANY configured token —
    the legacy shared secret OR any per-spoke SERVICE_TOKEN_* (e.g. the hub's
    SERVICE_TOKEN_HUB). Evaluates all candidates with no early return so response
    timing doesn't reveal which (if any) matched. False if nothing is configured
    or the presented token is empty/unmatched."""
    sent = (sent or "").strip()
    if not sent:
        return False
    matched = False
    tok = service_token(env)
    if tok and hmac.compare_digest(sent, tok):
        matched = True
    for _t in _per_spoke_tokens():
        if hmac.compare_digest(sent, _t):
            matched = True
    return matched


def header_authed(headers, header: str = TOKEN_HEADER, env: str = TOKEN_ENV) -> bool:
    try:
        sent = headers.get(header)
    except AttributeError:
        sent = None
    return token_matches(sent, env)
