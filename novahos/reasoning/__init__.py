"""The reasoning-layer seam (Master Blueprint §5).

Agents reason through a pluggable backend rather than hard-coded handlers. The default is a
deterministic offline stub (:class:`LocalReasoningProvider`) so the system runs with zero
configuration and the agent contract is fully testable without any API key.

This package is deliberately decoupled from WARDEN: WARDEN stays deterministic and LLM-free
and must never import from here.

Upgrading the brain: a litellm-backed provider (consistent with `novahos.llm`, which already
speaks litellm) — or a self-hosted model — can be returned from :func:`get_provider` when a
reasoning model/key is configured. The seam (`provider.py`) is the stable contract; agent
logic never changes.
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
    reason with no API key. A litellm/cloud-backed provider can be slotted in here later
    (gated on a configured reasoning model) without touching any agent logic.
    """
    return LocalReasoningProvider()
