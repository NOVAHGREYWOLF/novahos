"""Service-to-service auth — the PRODUCER half of the two-way mesh. (Rails; stdlib.)

Every app validates inbound calls the same way: a shared secret in the ``X-Service-Token``
header, checked constant-time against ``LEADFUEL_SERVICE_TOKEN``. The API stays OFF until
that env is set, so nothing opens a hole by default. Framework-agnostic (any headers mapping).
"""
from __future__ import annotations

import hmac
import logging
import os

log = logging.getLogger(__name__)

TOKEN_ENV = "LEADFUEL_SERVICE_TOKEN"
TOKEN_HEADER = "X-Service-Token"


def service_token(env: str = TOKEN_ENV) -> str:
    return (os.environ.get(env) or "").strip()


HUB_TOKEN_ENV = "SERVICE_TOKEN_HUB"


def own_outbound_token_env() -> str | None:
    """The env var holding THIS service's own outbound token, or None if undecidable.

    Derived the SAME way :func:`novahos.service_client._mesh_token` derives the token this
    service PRESENTS: the single ``SERVICE_TOKEN_*`` that is not ``SERVICE_TOKEN_HUB``. Using
    one rule for both halves is the point — the token a service sends and the tokens it accepts
    cannot drift apart if they are computed from the same fact.

    * On a SPOKE the env holds exactly ``SERVICE_TOKEN_<SELF>`` plus ``SERVICE_TOKEN_HUB``
      (kept in order to recognise the hub inbound), so removing HUB leaves precisely the self
      token and this returns its name.
    * On the HUB the env holds every spoke's token, so there is no single answer and this
      returns ``None``. That is correct rather than a limitation: every spoke calls the hub
      presenting its own token, so the hub genuinely must accept all of them inbound.

    Returns ``None`` rather than guessing whenever it cannot tell. A wrong answer here would
    silently exclude a sibling's token and 403 a legitimate caller.
    """
    names = [k for k, v in os.environ.items()
             if k.startswith("SERVICE_TOKEN_") and (v or "").strip() and k != HUB_TOKEN_ENV]
    return names[0] if len(names) == 1 else None


def _per_spoke_tokens() -> list[str]:
    """Every per-spoke token (SERVICE_TOKEN_*) this service accepts INBOUND.

    Lets a service recognise the hub (SERVICE_TOKEN_HUB) and any sibling by its own token, in
    addition to the legacy shared LEADFUEL_SERVICE_TOKEN — the inbound half of the per-spoke
    mesh.

    **Excludes this service's OWN outbound token.** That exclusion is the security property,
    not an optimisation. A service presents its own token on every call it makes, so every
    callee receives it and anything that logs a request records it. Accepting it inbound lets
    any of them replay it back and be authenticated as a trusted mesh peer.

    The earlier version of this function accepted every ``SERVICE_TOKEN_*`` in the environment
    on the stated grounds that it "accepts MORE tokens, never fewer". That rationale was the
    defect: a spoke's env holds the tokens of every sibling it calls, so one leaked token
    opened the inbound door of every service holding it — collapsing per-spoke isolation back
    to "one token opens everything", which is the arrangement the per-spoke migration existed
    to end. lucid's ``app/suite.py`` had already found this and excluded its own token locally;
    lucid's ``test_superset_of_shared_core`` is what caught the kernel widening underneath it.

    ``SERVICE_TOKEN_HUB`` is NEVER the excluded token, by construction of
    :func:`own_outbound_token_env`. This matters: on novahub that one secret does two jobs —
    the hub presents it outbound to spokes AND the cron services present it inbound to the hub
    (``scripts/cron_tick.py``). Excluding it would 403 every cron tick, a failure novahub's own
    ``app.py`` records having suffered twice from the adjacent mismatch. Splitting that secret
    in two is a config change with a deploy ordering constraint, and it cannot be done here.
    """
    own = own_outbound_token_env()
    out: list[str] = []
    for k, v in os.environ.items():
        if k.startswith("SERVICE_TOKEN_") and k != own:
            v = (v or "").strip()
            if v:
                out.append(v)
    return out


def is_enabled(env: str = TOKEN_ENV) -> bool:
    """True iff ANY service token this service ACCEPTS is configured — the legacy shared
    token or a per-spoke SERVICE_TOKEN_* other than its own. Staying enabled on per-spoke
    tokens is what lets the legacy LEADFUEL_SERVICE_TOKEN be RETIRED without 503-ing /api.

    One configuration changes answer now, deliberately: a service holding ONLY its own
    outbound token, with neither SERVICE_TOKEN_HUB nor the legacy shared token, used to
    report enabled and now reports disabled. It was only ever "enabled" by accepting its
    own outbound secret, which is the hole. A surface that can authenticate nobody should
    answer 503 rather than authenticate a replay, and 503 is at least loud. The warning
    below fires so this never has to be diagnosed from a bare 503."""
    if bool(service_token(env)) or bool(_per_spoke_tokens()):
        return True
    own = own_outbound_token_env()
    if own:
        _warn_self_only(own)
    return False


_warned_self_only = False


def _warn_self_only(own: str) -> None:
    """Say exactly why /api is closed, once, when the only token present is our own."""
    global _warned_self_only
    if _warned_self_only:
        return
    _warned_self_only = True
    log.warning(
        "[novahos.service_auth] mesh DISABLED: %s is the only service token set, and a "
        "service's own outbound token must not authenticate inbound (it is presented on "
        "every call this service makes, so any callee could replay it). Set %s to recognise "
        "the hub, or %s for the legacy shared secret.", own, HUB_TOKEN_ENV, TOKEN_ENV)


def token_matches(sent: str | None, env: str = TOKEN_ENV) -> bool:
    """Constant-time compare of a presented token against every token this service ACCEPTS
    — the legacy shared secret or any per-spoke SERVICE_TOKEN_* other than its own (e.g. the
    hub's SERVICE_TOKEN_HUB). Evaluates all candidates with no early return so response
    timing doesn't reveal which (if any) matched. False if nothing is configured or the
    presented token is empty/unmatched.

    NOT accepted: this service's own outbound token — see :func:`_per_spoke_tokens`. If that
    token's VALUE is also set under another name (both falling back to the same shared
    secret, say), it still matches through that other name. Refusing it there would mean
    refusing the hub, so the value stays accepted and the duplication is the thing to fix."""
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
