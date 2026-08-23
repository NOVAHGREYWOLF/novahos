"""LLM gateway over LiteLLM — shared by all agents. (Substrate.)

`reason()` = Opus-tier; `classify()` = cheap Haiku-tier. Nothing in the foundation imports
this — WARDEN stays deterministic.

THE ONE DOOR OUT (THE_DOOR.md law 9)
────────────────────────────────────
Every cloud model call below is pinned, PER CALL, to novahub's gateway — which runs the human
spend approval, the daily ceiling and the metered row before anything reaches a vendor — and
RAISES when the gateway is unconfigured. It never falls back to calling a vendor directly.

WHY A LIBRARY NEEDS THIS MORE THAN A SERVICE DOES, NOT LESS. Grep this repo for
ANTHROPIC_API_KEY and you find nothing — not one occurrence, in any file. That reads like
safety and is the opposite of it. litellm resolves BOTH halves of the call from the AMBIENT
PROCESS ENVIRONMENT, and both chains end at the vendor (read in litellm 1.98.0, main.py:2744
and :2748):

    api_key  = api_key  or litellm.anthropic_key or litellm.api_key
                        or os.environ.get("ANTHROPIC_API_KEY")
    api_base = api_base or litellm.api_base or get_secret("ANTHROPIC_API_BASE")
                        or get_secret("ANTHROPIC_BASE_URL")
                        or "https://api.anthropic.com/v1/messages"

So before this change ``reason()`` reached the vendor using whatever key its HOST happened to
hold, while never naming that key anywhere in this tree. That is the whole hazard of a library:
a service that deletes its own ANTHROPIC_API_KEY and then imports this one has not closed its
door, it has moved the door one import deeper — into a dependency whose diff it does not read
and whose environment it does not think of as its own. A transitive dependency is a door. The
estate-wide scan for ANTHROPIC_API_KEY scored this repo 0, and 0 was the most misleading number
in that table: it measured whether the credential was NAMED here, when what mattered was
whether it was USED here.

WHO ACTUALLY REACHES THIS. Established by reading the consumers rather than assuming: the four
call sites are ``agents/apollo/wordsmith.py``, ``agents/apollo/curator.py``,
``agents/athena/oracle.py`` and ``agents/croesus/advisor.py``. Live callers are novahound
(imports ``novahos.agents.apollo`` and ``novahos.llm`` directly in ``compose.py``) and lucid
(``novahos.agents.resolve("croesus", "assess")`` in ``app/experts/steward.py``). echo, icp,
novaherald, novahub, odyssey, novahawk and wolfos pin this library but import only
``warden_runtime`` / ``agent`` / ``mcp`` / ``sources`` / ``audit_trail``, so this path is dead
code in those processes today. It is one import away from not being, in any of them, which is
the reason to close it here rather than in each host.

WHERE THE CONFIG IS READ, AND WHY IT IS NOT IN config.py
────────────────────────────────────────────────────────
The gateway URL and token are read from ``os.environ`` AT CALL TIME, through the stdlib-only
:mod:`novahos.gateway_url` resolver — deliberately NOT through :class:`CoreSettings`. Three
reasons, all of which are specifically about being a library rather than a service:

1. ``settings = CoreSettings()`` runs at IMPORT of ``novahos.config``, snapshotting the
   environment at whatever instant the host first touched the kernel. Hosts touch it at wildly
   different instants — novahound imports ``novahos.llm`` inside a request handler, lucid
   imports ``novahos.agents`` lazily inside ``_resolve_croesus()`` — and a host that loads its
   secrets after that first import would snapshot an empty gateway URL. Reading at call time
   deletes the ordering question rather than documenting it.
2. ``CoreSettings`` is configured with ``env_file=".env"``, so it also reads a dotenv file out
   of the host's working directory. That is a config source the HOST did not choose. Tolerable
   for a model id; not for the value that decides whether spend is gated.
3. ``CoreSettings`` needs pydantic-settings, which lives in the ``substrate`` EXTRA. A guard
   that cannot load in a half-installed environment is a guard that can be missing, and the
   half-installed environment is exactly where you want it loudest.

Using the same module and the same two variable names as echo and NovahPrime is the point: one
definition of what this setting means, estate-wide. The model ids stay in ``CoreSettings``,
because those are routing rather than credentials and a wrong one fails loudly at the gateway.

Hosts that would rather not mutate ``os.environ`` can call :func:`configure_gateway` instead.
It runs through the identical validation, so it is a convenience, never a bypass.

METERING (audit P0: the kernel used to bill money and record NOTHING). Every paid call
through this gateway is now accounted for exactly once, by one of two owners:

  1. HOST-OWNED (opt-in capture): a host app brackets a unit of work with
     ``start_usage_capture()`` / ``collect_usage()`` and writes the rows to its own
     ledger. Thread-local, so it survives the asyncio.run() boundary that sync callers
     (e.g. Signal's APOLLO path in compose.py) use. Unchanged.
  2. KERNEL-OWNED (fallback): when NO capture is active, the gateway writes the row to
     the suite-shared ``ai_usage`` table itself.

The two are MUTUALLY EXCLUSIVE by construction, so nothing is counted twice. Before this,
case 2 was a silent no-op, which meant every unbracketed caller — the ATHENA, CROESUS and
APOLLO agents, and any future consumer — spent Opus money that landed in no store. Metering
was opt-in, so the DEFAULT was dark; that is the defect this closes.

Metering NEVER breaks a call: every path is safe-wrapped. But it is never silent either —
if the row cannot be written, that is logged at WARNING (once per process for config
problems), because a dead meter that logs at debug is how spend goes missing for a month.

Attribution: call ``set_account(email)`` on the thread that drives the work to tie kernel
spend to a customer. Unset is recorded as NULL rather than dropped, so the spend is still
visible even when the caller forgot.

KNOWN CONSEQUENCE OF ROUTING THROUGH THE GATEWAY — READ BEFORE DEPLOY
────────────────────────────────────────────────────────────────────
The metering above is deliberately UNCHANGED by this migration, and that leaves a live
double-count to resolve separately. novahub's gateway hands each call to
``llm_client.call_claude``, which writes the spend to the ``llm_usage`` meter AND to the
suite-shared ``ai_usage`` ledger (novahub PR #456). ``_emit_shared()`` below writes to
``ai_usage`` too. Once the gateway is deployed and a host bumps its novahos pin, one kernel
call can therefore produce TWO ``ai_usage`` rows: the gateway's and the kernel's.

It is stated here rather than fixed here on purpose. Egress and accounting are two changes,
and an accounting bug introduced alongside an egress change is invisible until a bill arrives.
Nothing double-counts yet: ``/llm/v1/messages`` is not deployed (verified — it answers 404
while ``/healthz`` answers 200), and every consumer that reaches this module is pinned to an
older SHA. So there is time to do it deliberately, and whoever bumps the first pin owns closing
it. The same question applies to the host-owned capture path, since novahound's ``compose.py``
writes its collected rows to ``ai_usage`` as well.

One consumer is NOT pinned by SHA: ``wolfos/lucid/requirements.txt`` tracks
``novahos.git@main``, so it picks this change up on its next build with no pin bump. That is
safe only because wolfos imports ``novahos.sources``, ``novahos.warden`` and
``novahos.sources.discovery`` and never reaches this module — checked, not assumed. It is
listed here because "pinned by SHA, so nothing moves until someone bumps it" is the assumption
this change rests on, and it is not true of every consumer.

Do not "fix" it by making the kernel stop writing. A silent meter is the defect the METERING
section above exists to have closed; trading a double-count for darkness is not an improvement.
"""
import json
import logging
import os
import threading

import litellm

from . import gateway_url
from .config import settings

# Re-exported so callers catch the SAME exception the resolver raises. A second exception type
# for "we refused to spend" would read to a caller as an unexpected crash.
from .gateway_url import GatewayMisconfigured, GatewayNotConfigured  # noqa: F401

log = logging.getLogger(__name__)

_capture = threading.local()
_account = threading.local()

_engine = None            # lazily-built async engine for the shared ledger
_engine_unavailable = False   # latches after one failure so we warn once, not per call

# Process-global, unlike the thread-locals above: capture and account bracket a unit of WORK,
# whereas this is a deployment fact about the process. Empty = read os.environ only.
_gateway_override: dict[str, str] = {}
_warned_host_key = False      # latches so the host-key warning is once per process, not per call


def configure_gateway(*, url: str | None = None, token: str | None = None) -> None:
    """Set this process's gateway URL/token in code, instead of via the environment.

    For hosts that configure their dependencies explicitly rather than by mutating
    ``os.environ``. Values set here take precedence over the environment for THIS library
    only, and are validated by exactly the same resolver — so this is a convenience, never a
    bypass: a vendor URL or a vendor-shaped token is refused here just as loudly as it is
    when it arrives from the environment. Pass ``None`` to leave a field to the environment;
    pass ``""`` to clear an override back to the environment."""
    for key, val in ((gateway_url.CANONICAL_URL_ENV, url),
                     (gateway_url.CANONICAL_TOKEN_ENV, token)):
        if val is None:
            continue
        if val.strip():
            _gateway_override[key] = val.strip()
        else:
            _gateway_override.pop(key, None)


def _gateway_env() -> dict:
    """The environment the resolver reads: ``os.environ``, with any override on top."""
    if not _gateway_override:
        return os.environ
    merged = dict(os.environ)
    merged.update(_gateway_override)
    return merged


def _warn_if_host_holds_vendor_key() -> None:
    """Say so, once, if the HOST process still carries a vendor key.

    novahos cannot delete it and must not refuse because of it — every one of the seven hosts
    legitimately still holds one until its own migration lands and the variable is removed.
    But while it is present, any code in the process that calls litellm WITHOUT pinning
    api_base still reaches the vendor with it, and this module's fail-closed behaviour says
    nothing whatsoever about those paths. Silence there would be its own small lie.

    Presence only. The value is never read into a variable and never logged."""
    global _warned_host_key
    if _warned_host_key or not os.environ.get("ANTHROPIC_API_KEY"):
        return
    _warned_host_key = True
    log.warning(
        "[novahos.llm] ANTHROPIC_API_KEY is set in this process. novahos does not use it — "
        "every call from here is pinned to the gateway — but any OTHER litellm or SDK call in "
        "this host that does not pin api_base will reach the vendor directly with it, "
        "unmetered and unapproved. Delete it once this service's own migration is deployed.")


#: Model prefixes litellm routes to infrastructure WE run (OLLAMA_API_BASE, default
#: http://localhost:11434). These never reach a vendor, so they must NOT be pinned at the
#: gateway: doing so would push text a host deliberately kept on its own box out to a vendor,
#: which is the exact inversion of why a host chose a local model. Everything NOT on this list
#: is treated as cloud and REQUIRES the door — an unknown prefix fails closed rather than
#: being assumed safe.
_SELF_HOSTED_PREFIXES = ("ollama/", "ollama_chat/")


def is_self_hosted(model: str) -> bool:
    """True when `model` runs on the host's own infra and needs no gateway."""
    return (model or "").startswith(_SELF_HOSTED_PREFIXES)


def _route(model: str) -> tuple[str, dict]:
    """The model id to send, plus the kwargs that pin this call at the ONE door.

    Returns ``(model, kwargs)``; splat the kwargs into ``litellm.acompletion``. For a
    self-hosted model the kwargs are empty and nothing is redirected. For a cloud model they
    carry ``api_base`` + ``api_key``, and this RAISES :class:`GatewayNotConfigured` when either
    is missing — so no cloud call is attempted at all.

    PER-CALL, not an env var and not the ``litellm.api_base`` global. All three were read in
    litellm 1.98.0 to decide this, and the two rejected options fail in opposite directions:

    * the ENV VARS (``ANTHROPIC_API_BASE`` / ``ANTHROPIC_BASE_URL``) are read only as the LAST
      fallback before a hardcoded vendor URL. ``main.py:2748`` is literally
      ``api_base or litellm.api_base or get_secret("ANTHROPIC_API_BASE") or
      get_secret("ANTHROPIC_BASE_URL") or "https://api.anthropic.com/v1/messages"``. A dropped
      Railway variable, a typo, a container that does not inherit the env — none of those is an
      error there. Each is a silent direct call to the vendor that SUCCEEDS.
    * the ``litellm.api_base`` GLOBAL is worse, because it is read BEFORE the per-call value on
      the ollama path: ``main.py:4225`` is ``litellm.api_base or api_base or
      get_secret("OLLAMA_API_BASE") or "http://localhost:11434"``. Setting the global would drag
      a host that deliberately runs a local model through the gateway and out to a vendor — the
      exact inversion of why that host chose a local model.

    Per-call ``api_base`` is first in the chain on the cloud path and is ignored on the local
    one. It is the only one of the three that can fail closed, and the only one that cannot
    reach past this module into a host's other litellm usage.

    The ``anthropic/`` prefix pins provider resolution to the model id we send rather than
    leaving it to the installed version's bundled model table. On 1.98.0 both configured
    defaults resolve to the anthropic provider without it, so today it is belt-and-braces — but
    the floor in pyproject.toml is 1.40, the ids are host-overridable via ``REASONING_MODEL``,
    and a model id an older table does not know is exactly the case where resolution goes
    somewhere else. Verified on 1.98.0 that litellm strips the prefix again before the wire
    (``get_llm_provider("anthropic/claude-opus-4-8") -> ("claude-opus-4-8", "anthropic", …)``),
    so the gateway still receives the bare id and the approval email still names the real model.
    """
    if is_self_hosted(model):
        return model, {}          # host's own infra — never leaves it, never needs the door

    _warn_if_host_holds_vendor_key()
    env = _gateway_env()
    # messages_url() appends /v1/messages explicitly rather than trusting litellm to. 1.98.0
    # DOES append it when absent (main.py:2759), but the floor here is litellm>=1.40 and
    # versions below 1.45 append nothing — so the full path is the only value that is correct
    # across the whole supported range, and an explicit append is greppable where a version
    # assumption is not. messages_url() also refuses a URL that names a vendor, and token()
    # refuses a value shaped like a vendor key: both otherwise WORK, silently, past the door.
    gate = {"api_base": gateway_url.messages_url(env),
            "api_key": gateway_url.token(env)}
    # Name the person the spend belongs to, so the gateway's approval email says WHO wanted it
    # rather than only that something did. Absent, the hub attributes it to the calling service.
    # The hub reads this off the request (novahub app.py llm_gateway_messages), alongside the
    # x-api-key litellm sends the token as by default (verified: anthropic/common_utils.py
    # _make_api_key_auth_header defaults to x-api-key). Never put x-api-key or authorization in
    # here — caller headers win the merge, which would override the gateway token itself.
    acting = _account_email()
    if acting:
        gate["extra_headers"] = {"X-Acting-Email": acting}
    return (model if "/" in model else f"anthropic/{model}"), gate


def set_account(email: str | None) -> None:
    """Attribute subsequent kernel LLM calls on THIS thread to a customer.

    Thread-local to match the capture bracket. Safe to call with None to clear."""
    _account.email = ((email or "").strip().lower() or None)


def _account_email() -> str | None:
    return getattr(_account, "email", None)


def _shared_engine():
    """Async engine for the suite-shared ai_usage table, or None (warned once)."""
    global _engine, _engine_unavailable
    if _engine is not None or _engine_unavailable:
        return _engine
    url = (os.environ.get("SHARED_DATABASE_URL") or "").strip()
    if not url:
        _engine_unavailable = True
        log.warning("[novahos.llm] SHARED_DATABASE_URL unset — kernel LLM spend cannot be "
                    "metered and will NOT appear in suite COGS")
        return None
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(url, pool_size=1, max_overflow=2, pool_pre_ping=True)
        return _engine
    except Exception:  # noqa: BLE001 — no driver / bad URL: warn once, never raise
        _engine_unavailable = True
        log.warning("[novahos.llm] could not build the shared-ledger engine — kernel LLM "
                    "spend will NOT be metered", exc_info=True)
        return None


async def _emit_shared(resp, model: str, tokens_in: int, tokens_out: int) -> None:
    """Write ONE ai_usage row for a kernel call the host did not capture.

    Only reached when no capture bracket is active, so it can never double-count a
    host-owned row. Never raises: accounting must not break the agent that called us."""
    eng = _shared_engine()
    if eng is None:
        return
    try:
        try:
            cost = float(litellm.completion_cost(completion_response=resp) or 0.0)
        except Exception:  # noqa: BLE001 — an unpriced model is still worth recording
            cost = 0.0
        from sqlalchemy import text as _t
        service = (os.environ.get("NOVAHOS_SERVICE") or "novahos").strip()[:32]
        async with eng.begin() as conn:
            await conn.execute(_t(
                "INSERT INTO ai_usage "
                "  (service, account_email, task, model, tokens_in, tokens_out, cost_usd, at) "
                "VALUES (:svc, :acct, :task, :model, :tin, :tout, :cost, NOW())"
            ), {"svc": service, "acct": _account_email(), "task": _task.get_task(),
                "model": (model or "")[:64], "tin": tokens_in, "tout": tokens_out,
                "cost": cost})
    except Exception:  # noqa: BLE001
        log.warning("[novahos.llm] shared ai_usage insert failed for model=%s — this spend "
                    "is NOT recorded", model, exc_info=True)


async def emit_usage(*, task: str, model: str, cost_usd: float,
                     tokens_in: int = 0, tokens_out: int = 0,
                     account_email: str | None = None) -> None:
    """Write ONE row to the suite-shared ai_usage ledger.

    The kernel's public metering entry point for NON-LLM paid vendors (transcription,
    enrichment, anything billed per unit rather than per token). LLM calls go through
    the gateway and are metered automatically; this is for everything else.

    Never raises. Never silent: a failed write logs at WARNING."""
    eng = _shared_engine()
    if eng is None:
        return
    try:
        from sqlalchemy import text as _t
        service = (os.environ.get("NOVAHOS_SERVICE") or "novahos").strip()[:32]
        async with eng.begin() as conn:
            await conn.execute(_t(
                "INSERT INTO ai_usage "
                "  (service, account_email, task, model, tokens_in, tokens_out, cost_usd, at) "
                "VALUES (:svc, :acct, :task, :model, :tin, :tout, :cost, NOW())"
            ), {"svc": service, "acct": (account_email or _account_email()),
                "task": (task or "kernel.call")[:32], "model": (model or "")[:64],
                "tin": int(tokens_in or 0), "tout": int(tokens_out or 0),
                "cost": float(cost_usd or 0.0)})
    except Exception:  # noqa: BLE001
        log.warning("[novahos.llm] shared ai_usage insert failed for task=%s model=%s — "
                    "this spend is NOT recorded", task, model, exc_info=True)


class _Task:
    """Thread-local label for the row's `task` column (defaults per gateway fn)."""
    _tl = threading.local()

    def set(self, name: str) -> None:
        self._tl.name = name

    def get_task(self) -> str:
        return (getattr(self._tl, "name", None) or "kernel.call")[:32]


_task = _Task()


def start_usage_capture() -> None:
    """Begin capturing reason()/classify() usage on this thread (resets any prior)."""
    _capture.rows = []


def collect_usage() -> list:
    """Return the usage rows captured since start_usage_capture() and stop capturing.
    Each row: {model, prompt_tokens, completion_tokens}. Empty if none / not started."""
    rows = getattr(_capture, "rows", None)
    _capture.rows = None
    return rows or []


def _tokens(resp) -> tuple[int, int]:
    """(prompt_tokens, completion_tokens) from a LiteLLM response, 0 on anything odd."""
    u = getattr(resp, "usage", None)

    def _g(name):
        v = getattr(u, name, None)
        if v is None and isinstance(u, dict):
            v = u.get(name)
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    return _g("prompt_tokens"), _g("completion_tokens")


async def _meter(resp, model: str, task: str) -> None:
    """Account for ONE paid gateway call, exactly once.

    Capture active  -> the HOST owns the emit; we only hand it the row.
    No capture      -> the KERNEL owns it and writes ai_usage itself.
    Mutually exclusive, so a bracketed call is never counted twice. Never raises."""
    try:
        tin, tout = _tokens(resp)
        rows = getattr(_capture, "rows", None)
        if rows is not None:
            rows.append({"model": model, "prompt_tokens": tin, "completion_tokens": tout})
            return
        _task.set(task)
        await _emit_shared(resp, model, tin, tout)
    except Exception:  # noqa: BLE001 — accounting must never break the caller
        log.warning("[novahos.llm] metering failed for model=%s task=%s", model, task,
                    exc_info=True)


def _record(resp, model: str) -> None:
    """Back-compat shim: capture-only recording (no kernel-owned fallback).
    Kept so any external caller of this private helper keeps working."""
    rows = getattr(_capture, "rows", None)
    if rows is None:
        return
    tin, tout = _tokens(resp)
    rows.append({"model": model, "prompt_tokens": tin, "completion_tokens": tout})


async def reason(system: str, user: str, max_tokens: int = 2000, *,
                 task: str = "kernel.reason") -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    # _route() first, and OUTSIDE the call: an unconfigured gateway raises here, before a
    # socket is opened. Metering still records settings.reasoning_model, not the routed id, so
    # ledger rows keep the shape every existing report and reconciliation already reads.
    model, gate = _route(settings.reasoning_model)
    resp = await litellm.acompletion(model=model, messages=messages, max_tokens=max_tokens, **gate)
    await _meter(resp, settings.reasoning_model, task)
    return resp.choices[0].message.content or ""


async def classify(prompt: str, *, task: str = "kernel.classify") -> str:
    model, gate = _route(settings.cheap_model)
    resp = await litellm.acompletion(model=model,
                                     messages=[{"role": "user", "content": prompt}],
                                     max_tokens=400, **gate)
    await _meter(resp, settings.cheap_model, task)
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)
