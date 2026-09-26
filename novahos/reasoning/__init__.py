"""The reasoning-layer seam (Master Blueprint §5).

Agents reason through a pluggable backend rather than hard-coded handlers. The default is a
deterministic offline stub (:class:`LocalReasoningProvider`) so the system runs with zero
configuration and the agent contract is fully testable without any API key.

This package is deliberately decoupled from WARDEN: WARDEN stays deterministic and LLM-free
and must never import from here.

Upgrading the brain: a cloud-backed provider can be returned from :func:`get_provider` when a
reasoning model is configured. The seam (`provider.py`) is the stable contract; agent logic
never changes. Two rules bind whoever writes that provider.

**1. Reach the cloud through `novahos.llm`, never through litellm directly.** An earlier
version of this note justified that by saying novahos.llm "already speaks litellm", which is
the wrong reason and a dangerous one — speaking litellm is not the property that matters,
where it points is. `echo/app/llm.py` and `lucid/app/llm.py` both speak litellm, both open
with the line "LLM gateway wrapper over LiteLLM", and both call `acompletion` with no
`api_base` — so they meter the spend precisely and then send the request straight to the
vendor. The reason to use `novahos.llm` is specifically that `_route()` pins `api_base` and
`api_key` on each call and raises `GatewayNotConfigured` when either is missing, so an
unconfigured host makes no call at all. `tests/test_one_door_static.py` enforces this
statically; do not add an exemption to it.

**2. A cloud leg is a decision, never a fallback.** If a provider chain ever runs a local
model first, a local failure must raise rather than escalate to a vendor. Spending the
owner's money at a vendor they declined, because their own model had a bad minute, answers a
question nobody asked — and it is the failure mode a local/cloud provider pair invites by
default. `LocalReasoningProvider` has no cloud leg today, so there is nothing to escalate
from; the rule is written down here because the first person to add one will need it.
"""

from __future__ import annotations

from .local import LocalReasoningProvider
from .provider import ReasoningProvider, ReasoningResult

__all__ = [
    "ReasoningProvider",
    "ReasoningResult",
    "LocalReasoningProvider",
    "get_provider",
]


def get_provider() -> ReasoningProvider:
    """Return the default reasoning provider.

    Today this is the deterministic, zero-config :class:`LocalReasoningProvider` so agents
    reason with no API key. A cloud-backed provider can be slotted in here later, gated on a
    configured reasoning model, without touching any agent logic — subject to the two rules
    in this package's docstring: go through `novahos.llm`, and never fall back to a vendor
    when a local model fails.
    """
    return LocalReasoningProvider()
