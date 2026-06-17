"""LLM gateway over LiteLLM — shared by all agents. (Substrate.)

`reason()` = Opus-tier; `classify()` = cheap Haiku-tier. Nothing in the foundation imports
this — WARDEN stays deterministic.

USAGE CAPTURE (opt-in, additive): a host app can bracket a unit of work with
``start_usage_capture()`` / ``collect_usage()`` to retrieve the token usage of every
reason()/classify() call made on THIS thread in between (so it can cost + log the spend
to its own ledger). Off by default — when no capture is active these record nothing and
behave exactly as before. Thread-local, so it survives the asyncio.run() boundary that
sync callers (e.g. Signal's APOLLO path) use.
"""
import json
import threading

import litellm

from .config import settings

_capture = threading.local()


def start_usage_capture() -> None:
    """Begin capturing reason()/classify() usage on this thread (resets any prior)."""
    _capture.rows = []


def collect_usage() -> list:
    """Return the usage rows captured since start_usage_capture() and stop capturing.
    Each row: {model, prompt_tokens, completion_tokens}. Empty if none / not started."""
    rows = getattr(_capture, "rows", None)
    _capture.rows = None
    return rows or []


def _record(resp, model: str) -> None:
    rows = getattr(_capture, "rows", None)
    if rows is None:
        return  # no capture active — no-op
    u = getattr(resp, "usage", None)

    def _g(name):
        v = getattr(u, name, None)
        if v is None and isinstance(u, dict):
            v = u.get(name)
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    rows.append({"model": model,
                 "prompt_tokens": _g("prompt_tokens"),
                 "completion_tokens": _g("completion_tokens")})


async def reason(system: str, user: str, max_tokens: int = 2000) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    resp = await litellm.acompletion(model=settings.reasoning_model, messages=messages, max_tokens=max_tokens)
    _record(resp, settings.reasoning_model)
    return resp.choices[0].message.content or ""


async def classify(prompt: str) -> str:
    resp = await litellm.acompletion(model=settings.cheap_model,
                                     messages=[{"role": "user", "content": prompt}], max_tokens=400)
    _record(resp, settings.cheap_model)
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    return json.loads(text)
