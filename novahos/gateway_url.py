# VENDORED. The canonical copy is NOVAHGREYWOLF/novahub gateway_url.py.
#
# Copied rather than imported for the same reason echo vendors it: these are separate
# deployments with no shared package, and Python has no way to share runtime code across
# repos here without publishing one. If you change this file, change it in novahub first and
# copy it down, or the estate silently grows a second answer to the question this module
# exists to have one answer to.
#
# It is stdlib-only on purpose. That matters more here than anywhere else in the estate:
# novahos is a LIBRARY, installed into seven host processes, and `novahos[substrate]` is an
# EXTRA. A guard that needed pydantic-settings or litellm to load would be absent in exactly
# the half-installed environment where it is most needed. A guard that can be missing is not
# a guard.
#
# NOTE FOR THE PUBLIC REPO: novahos is public. This file names `leadfuel.cloud` in prose, as
# the canonical copy does. That is not a new disclosure — the same hostname is already the
# committed default in novahos/sources/_identity.py. It carries no secret, no token and no
# internal path. It was left identical to the canonical copy deliberately: a vendored file
# that quietly differs from its source is how two answers start.

"""One form for the gateway URL, and one place that decides what it means.

WHY THIS FILE EXISTS
────────────────────
Two services migrated to the gateway in the same week and chose opposite conventions for the
same setting:

    echo         LLM_GATEWAY_URL       = https://leadfuel.cloud/llm/v1/messages
    NovahPrime   NOVAH_LLM_GATEWAY_URL = https://leadfuel.cloud/llm

Both were correct *for their client*. litellm below 1.45 appends nothing to ``api_base``, so it
needs the full path; the Anthropic SDK appends ``/v1/messages`` to ``base_url`` itself, so
handing it the full path would produce ``/llm/v1/messages/v1/messages``. Neither author was
wrong. The estate was.

That is a live hazard rather than an aesthetic complaint, because of HOW each client fails.
litellm's ``api_base`` resolution chain ends at a hardcoded
``https://api.anthropic.com/v1/messages``. So a value copy-pasted between two services, or a
variable renamed in one place and not the other, does not raise. It silently reaches the vendor,
which is the exact outcome the gateway exists to make impossible. A misconfiguration that fails
loudly is a nuisance; this one fails quietly and bills you.

THE CANONICAL FORM IS ORIGIN + MOUNT, WITHOUT ``/v1/messages``
──────────────────────────────────────────────────────────────
    LLM_GATEWAY_URL=https://leadfuel.cloud/llm

Chosen because it is already what "base URL" means everywhere else here and in the vendors' own
SDKs: ``app.py``'s route docstring documents the no-code migration path as
``ANTHROPIC_BASE_URL=https://<hub>/llm``, and the SDK's ``base_url`` takes the same shape. A
setting that means the same thing as the thing it replaces is one fewer fact to remember.

It is also the only direction that is deterministic to convert. Trimming a known suffix is
exact. Deciding whether to APPEND one requires knowing which client library will read the value,
which the person typing a Railway variable does not.

Callers needing the full path call :func:`messages_url`. That is a one-line, explicit, greppable
append in code, rather than a convention someone has to keep in their head. ``novahos.llm``
speaks litellm, so it is one of the callers that appends.

WHAT THIS REFUSES, AND WHY EACH REFUSAL IS FAIL-CLOSED
──────────────────────────────────────────────────────
* **Unset** -> :class:`GatewayNotConfigured`. Absence of a decision is never permission.
* **Only the deprecated name set** -> :class:`GatewayNotConfigured`, naming both. A rename that
  silently falls back to the old variable is a rename that never finishes.
* **A vendor hostname** -> :class:`GatewayMisconfigured`. This is the load-bearing check. If the
  gateway URL is set to ``api.anthropic.com``, every call becomes a direct vendor call that
  LOOKS configured: unmetered, unapproved, invisible to the ledger. Nothing downstream can tell
  the difference, so it has to be caught here.
* **A non-HTTP scheme, or no host** -> :class:`GatewayMisconfigured`.
* **Plain http to a non-loopback host** -> :class:`GatewayMisconfigured`. The gateway token and
  the prompt both cross that hop.
* **A token that is obviously the vendor key** (``sk-ant-…``) -> :class:`GatewayMisconfigured`.
  This one is worth its own check because it is the single most likely wrong paste, and it
  *works*: the vendor accepts it, the call succeeds, and the gateway is bypassed silently.

The last two checks are lifted from NovahPrime's own implementation, which had them before this
module existed. Consolidating should not lose the better half of what it is consolidating.

None of these are warnings. A warning is a decision to continue.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit

CANONICAL_URL_ENV = "LLM_GATEWAY_URL"
CANONICAL_TOKEN_ENV = "LLM_GATEWAY_TOKEN"

#: Read only to produce a better error. Never used as a value — see the module docstring.
DEPRECATED_URL_ENVS = ("NOVAH_LLM_GATEWAY_URL",)
DEPRECATED_TOKEN_ENVS = ("NOVAH_LLM_GATEWAY_TOKEN",)

MESSAGES_PATH = "/v1/messages"

# Trimmed to reach origin+mount. Longest first, so /v1/messages wins over /v1.
_TRIM = (MESSAGES_PATH, "/v1")

# Vendor REGISTRABLE DOMAINS — deliberately not API hostnames. This list was
# "api.anthropic.com, api.openai.com, …" and the check was ``host in _VENDOR_HOSTS``, which is
# exact set membership. That accepted every one of these as a gateway:
#
#     https://anthropic.com/llm             the bare domain was never in the set
#     https://foo.api.anthropic.com/llm     a subdomain was never in the set
#     https://api.anthropic.com./llm        the trailing dot is the DNS root, and resolves to
#                                           the identical addresses
#
# Naming the registrable domain and matching on DNS LABEL BOUNDARIES covers all three at once,
# and needs no public-suffix list: a PSL is required to compute an UNKNOWN host's registrable
# domain, not to ask whether a host sits under one of a handful of KNOWN ones.
#
# Still deliberately short. This is a "did you point it at the vendor" check, not a general
# egress denylist — that job belongs to .github/actions/vendor-egress-gate/check.py, which is
# also why this file sits on that checker's allow list. A checker and a guard both have to name
# the hosts they guard against.
_VENDOR_DOMAINS = frozenset({
    "anthropic.com", "openai.com", "voyageai.com", "cohere.ai", "cohere.com",
    "groq.com", "together.xyz", "together.ai", "mistral.ai", "replicate.com",
    "deepgram.com", "assemblyai.com", "elevenlabs.io", "huggingface.co",
    "googleapis.com", "perplexity.ai", "x.ai",
})

#: Back-compat alias for the pre-2026-08-22 name. It was a set of API hostnames; it is now a
#: set of registrable domains, so a membership test against it is strictly broader than before.
#: odyssey's test_llm_one_door.py reads it by this name.
_VENDOR_HOSTS = _VENDOR_DOMAINS

# Plain http is tolerated only here: a local gateway during development. Everywhere else the
# token and the prompt both cross that hop in clear text.
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

# Vendor key prefixes. A token starting with one of these is not a gateway token, it is the
# credential the gateway exists to hold. Pasted into LLM_GATEWAY_TOKEN it does not fail: the
# vendor accepts it and the call succeeds, having gone nowhere near the door.
_VENDOR_KEY_PREFIXES = ("sk-ant-", "sk-proj-", "sk-or-", "gsk_", "pa-")


def _labels(host: str) -> tuple:
    """A hostname as its DNS labels: lowercased, root dot dropped, empties removed.

    ``api.anthropic.com.`` and ``api.anthropic.com`` are the same name. The trailing dot is the
    DNS root, every resolver returns the identical addresses for both, and before this function
    existed the dotted form was accepted as a gateway by every implementation in the estate —
    including the two that already matched subdomains correctly.
    """
    return tuple(part for part in host.strip().lower().rstrip(".").split(".") if part)


def _vendor_domain_of(host: str):
    """``(vendor_domain, "under" | "embedded")`` if this host is a vendor's, else ``None``.

    ``under``    the host IS a vendor domain, or sits beneath one. ``anthropic.com``,
                 ``api.anthropic.com`` and ``foo.api.anthropic.com`` all reach Anthropic.

    ``embedded`` the vendor's labels appear in the host but NOT at the end, so the name is
                 somebody else's: ``api.anthropic.com.evil.tld`` sits under ``evil.tld``. It
                 does not reach the vendor — it reaches whoever owns ``evil.tld``, carrying the
                 prompt and this service's gateway token, while reading to a human scanning a
                 variable list as though it were the vendor.

    Matching is on whole labels, which is the entire point. ``host.endswith("anthropic.com")``
    would refuse ``notanthropic.com``, a name with no relationship to the vendor at all, and a
    guard that refuses correct configurations is a guard people learn to route around.
    """
    labels = _labels(host)
    if not labels:
        return None
    ordered = sorted(_VENDOR_DOMAINS)  # sorted so the refusal message is deterministic
    for domain in ordered:
        want = tuple(domain.split("."))
        if len(labels) >= len(want) and labels[-len(want):] == want:
            return domain, "under"
    for domain in ordered:
        want = tuple(domain.split("."))
        for i in range(len(labels) - len(want)):  # stops before the tail, checked above
            if labels[i:i + len(want)] == want:
                return domain, "embedded"
    return None


class GatewayNotConfigured(RuntimeError):
    """The gateway is not configured. Refuse, rather than reach a vendor directly."""


class GatewayMisconfigured(RuntimeError):
    """The gateway IS configured, and configured to something that is not the gateway."""


def _env(source: dict | None) -> dict:
    return os.environ if source is None else source


def base_url(env: dict | None = None) -> str:
    """The gateway origin + mount: ``https://host/llm``. No trailing slash, no ``/v1``.

    Pass this straight to any client that appends the path itself (the Anthropic SDK's
    ``base_url``, or ``ANTHROPIC_BASE_URL``)."""
    e = _env(env)
    raw = (e.get(CANONICAL_URL_ENV) or "").strip()

    if not raw:
        stale = [n for n in DEPRECATED_URL_ENVS if (e.get(n) or "").strip()]
        if stale:
            raise GatewayNotConfigured(
                f"{CANONICAL_URL_ENV} is not set, but the deprecated {', '.join(stale)} is. "
                f"Rename it to {CANONICAL_URL_ENV} and drop any /v1 or /v1/messages suffix: "
                f"the canonical value is the origin plus mount, e.g. https://host/llm. "
                f"Not falling back to the old name on purpose — a rename that silently keeps "
                f"working is a rename that never finishes.")
        raise GatewayNotConfigured(
            f"{CANONICAL_URL_ENV} is not set. Refusing to call a model vendor directly. "
            f"Set it to the gateway origin plus mount, e.g. https://host/llm")

    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https"):
        raise GatewayMisconfigured(f"{CANONICAL_URL_ENV}={raw!r} is not an http(s) URL.")
    if not parts.netloc:
        raise GatewayMisconfigured(f"{CANONICAL_URL_ENV}={raw!r} has no host.")

    host = (parts.hostname or "").lower()
    if not host.isascii():
        raise GatewayMisconfigured(
            f"{CANONICAL_URL_ENV}={raw!r} has a non-ASCII hostname. Comparing a Unicode name "
            f"against the vendor list would need a homograph table, so it is refused "
            f"rather than guessed at. If the host really is an internationalised name, "
            f"set its punycode (xn--…) form, which this check reads.")

    match = _vendor_domain_of(host)
    if match:
        domain, how = match
        if how == "under":
            raise GatewayMisconfigured(
                f"{CANONICAL_URL_ENV} points at {host}, which is {domain} — a model vendor, not the "
                f"gateway. Every call would be a direct vendor call that looks "
                f"configured: unmetered, unapproved, and invisible to the spend "
                f"ledger. Point it at the gateway.")
        owner = ".".join(_labels(host)[-2:])
        raise GatewayMisconfigured(
            f"{CANONICAL_URL_ENV} points at {host}, which contains the vendor domain {domain} but is "
            f"not under it — this name belongs to whoever owns {owner}. It does not "
            f"reach {domain}; it reaches them, carrying the prompt and this service's "
            f"gateway token, while reading like the vendor to anyone scanning a "
            f"variable list. If it really is your own host, give it a name that does "
            f"not impersonate a vendor.")
    if parts.scheme == "http" and host not in _LOOPBACK_HOSTS:
        raise GatewayMisconfigured(
            f"{CANONICAL_URL_ENV}={raw!r} is plain http to a remote host. The gateway token and "
            f"the prompt both cross that hop. Use https, or a loopback address for local work.")

    url = raw.rstrip("/")
    for suffix in _TRIM:
        if url.lower().endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
            break
    if not urlsplit(url).netloc:
        raise GatewayMisconfigured(
            f"{CANONICAL_URL_ENV}={raw!r} leaves nothing after trimming "
            f"{' or '.join(_TRIM)}.")
    return url


def messages_url(env: dict | None = None) -> str:
    """``base_url()`` plus ``/v1/messages``.

    For clients that do NOT append the path themselves. litellm's ``api_base`` is the one that
    matters here, because its own fallback chain ends at a hardcoded vendor URL."""
    return base_url(env) + MESSAGES_PATH


def token(env: dict | None = None) -> str:
    """This service's OWN gateway token. Never the vendor key."""
    e = _env(env)
    tok = (e.get(CANONICAL_TOKEN_ENV) or "").strip()
    if tok:
        low = tok.lower()
        if any(low.startswith(p) for p in _VENDOR_KEY_PREFIXES):
            raise GatewayMisconfigured(
                f"{CANONICAL_TOKEN_ENV} looks like a model vendor's API key, not this service's "
                f"gateway token. That paste does not fail: the vendor accepts the key and the "
                f"call succeeds, having gone nowhere near the door. Generate a gateway token "
                f"instead (docs/LLM_GATEWAY.md), and delete the vendor key from this service.")
        return tok
    stale = [n for n in DEPRECATED_TOKEN_ENVS if (e.get(n) or "").strip()]
    if stale:
        raise GatewayNotConfigured(
            f"{CANONICAL_TOKEN_ENV} is not set, but the deprecated {', '.join(stale)} is. "
            f"Rename it to {CANONICAL_TOKEN_ENV}.")
    raise GatewayNotConfigured(
        f"{CANONICAL_TOKEN_ENV} is not set. This is the service's OWN gateway token, "
        f"not ANTHROPIC_API_KEY.")
