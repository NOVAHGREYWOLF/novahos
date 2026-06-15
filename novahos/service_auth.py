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


def is_enabled(env: str = TOKEN_ENV) -> bool:
    return bool(service_token(env))


def token_matches(sent: str | None, env: str = TOKEN_ENV) -> bool:
    tok = service_token(env)
    if not tok:
        return False
    sent = (sent or "").strip()
    return bool(sent) and hmac.compare_digest(sent, tok)


def header_authed(headers, header: str = TOKEN_HEADER, env: str = TOKEN_ENV) -> bool:
    try:
        sent = headers.get(header)
    except AttributeError:
        sent = None
    return token_matches(sent, env)
