"""The reasoning-layer seam: a pluggable backend agents reason through (Master Blueprint §5).

Agents in NOVAH propose actions and WARDEN disposes; the *reasoning* an agent does to
arrive at a proposal happens here, behind a single narrow interface. This keeps the choice
of brain — a deterministic local stub, a self-hosted model, or a cloud LLM — swappable
without touching agent logic.

Nothing in this module imports WARDEN, and WARDEN must never import this: WARDEN stays
deterministic and LLM-free (Doc #26 §2.4). The reasoning layer is allowed to be slow,
non-deterministic, or networked; WARDEN is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ReasoningResult:
    """The outcome of one reasoning call.

    `text` is the model's answer, `model` identifies the backend that produced it (useful for
    audit and for tests to assert which provider ran), and `meta` carries provider-specific
    extras (token counts, stop reason, etc.).
    """

    text: str
    model: str
    meta: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ReasoningProvider(Protocol):
    """A backend that can turn a prompt into a :class:`ReasoningResult`.

    Implementations may be deterministic (the local stub) or call out to a model. The
    contract is intentionally tiny so any backend — and any test double — can satisfy it.
    """

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        **kw: Any,
    ) -> ReasoningResult:
        """Reason about `prompt` and return a result.

        Args:
            prompt: The user/agent message to reason about.
            system: Optional system instruction framing the reasoning.
            max_tokens: Soft cap on the length of the generated answer.
            **kw: Provider-specific options (e.g. temperature, model overrides).
        """
        ...
