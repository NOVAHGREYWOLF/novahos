"""LLM gateway over LiteLLM — shared by all agents. (Substrate.)

`reason()` = Opus-tier; `classify()` = cheap Haiku-tier. Nothing in the foundation imports
this — WARDEN stays deterministic.

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
"""
import json
import logging
import os
import threading

import litellm

from .config import settings

log = logging.getLogger(__name__)

_capture = threading.local()
_account = threading.local()

_engine = None            # lazily-built async engine for the shared ledger
_engine_unavailable = False   # latches after one failure so we warn once, not per call


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
    resp = await litellm.acompletion(model=settings.reasoning_model, messages=messages, max_tokens=max_tokens)
    await _meter(resp, settings.reasoning_model, task)
    return resp.choices[0].message.content or ""


async def classify(prompt: str, *, task: str = "kernel.classify") -> str:
    resp = await litellm.acompletion(model=settings.cheap_model,
                                     messages=[{"role": "user", "content": prompt}], max_tokens=400)
    await _meter(resp, settings.cheap_model, task)
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)
