"""The base Agent — the three-layer, propose-through-WARDEN contract (Doc #26 §3).

Every agent: reads context (input layer), reasons and *proposes* actions (reasoning layer),
and writes only after WARDEN approval (action layer). This base class makes that structural:
an agent can never execute a side-effecting handler except through `act()`, which routes the
request through WARDEN first and runs the handler only on APPROVE.

The Constitutional Preamble is injected into every agent's system prompt here — it cannot be
skipped. Agents also respect their onboarding state: in SHADOW mode they propose but never
execute; only an agent in ACTIVE (gradual rollout) state executes approved actions.

Ported from the NovahPrime foundation; rewired onto novahos.constitution / .warden_runtime / .reasoning.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..constitution import inject_preamble, preamble_present
from ..warden_runtime.gate import WardenDecision
from ..warden_runtime.types import ActionRequest, PrivacyTier
from .manifest import AgentManifest


class OnboardingState(IntEnum):
    """The eight-step onboarding progression (Doc #26 §6). Ordered."""

    REGISTERED = 0
    MANIFEST_VALIDATED = 1
    CONSTITUTION_BOUND = 2
    WARDEN_REGISTERED = 3
    MCP_VERIFIED = 4
    SANDBOX_PASSED = 5
    SHADOW = 6
    USER_APPROVED = 7
    ACTIVE = 8  # gradual rollout — the agent may now execute approved actions


# Handler signature: (payload, decision) -> output
Handler = Callable[[Any, WardenDecision], Any]


@dataclass
class AgentActionResult:
    """Outcome of an agent attempting an action."""

    decision: WardenDecision
    executed: bool
    output: Any = None
    shadow: bool = False

    @property
    def approved(self) -> bool:
        return self.decision.approved


class Agent:
    """Base class for every NOVAH agent."""

    def __init__(
        self,
        manifest: AgentManifest,
        warden,
        *,
        role_prompt: str,
        mcp_boundary=None,
        reasoning=None,
    ) -> None:
        self.manifest = manifest
        self.name = manifest.name
        self.warden = warden
        self.role_prompt = role_prompt
        self.system_prompt = inject_preamble(role_prompt)
        self.mcp_boundary = mcp_boundary
        self.state = OnboardingState.REGISTERED
        self._handlers: dict[str, Handler] = {}
        self._reasoning = reasoning
        # Optional system services, injected at boot (None until then). Agents that use them
        # degrade gracefully when they are absent (e.g. in isolated unit tests).
        self.episodic = None
        self.semantic = None
        self.learner = None
        if not preamble_present(self.system_prompt):  # invariant, never expected to fail
            raise ValueError(f"Constitutional Preamble missing from {self.name}'s prompt.")

    @property
    def active(self) -> bool:
        return self.state is OnboardingState.ACTIVE

    # --- reasoning layer (input/reasoning only — never bypasses WARDEN) ---

    @property
    def reasoning(self):
        """The agent's reasoning provider. Defaults to the system provider (deterministic local).
        Reasoning produces *text/proposals* only; any action still has to go through `act()`
        and WARDEN."""
        if self._reasoning is None:
            from ..reasoning import get_provider

            self._reasoning = get_provider()
        return self._reasoning

    def reason(self, prompt: str, *, system: str | None = None, max_tokens: int = 1024) -> str:
        """Reason over a prompt and return text. The agent's Constitution-bound system prompt is
        used by default, so the reasoning layer is always anchored to the Constitution."""
        result = self.reasoning.complete(
            prompt, system=system if system is not None else self.system_prompt, max_tokens=max_tokens
        )
        return result.text

    # --- capabilities ---

    def register_action(self, action: str, handler: Handler) -> None:
        """Bind a handler to an action name. Handlers run only after WARDEN approves."""
        self._handlers[action] = handler

    def handles(self, action: str) -> bool:
        return action in self._handlers

    @property
    def actions(self) -> list[str]:
        return list(self._handlers)

    # --- the propose / dispose contract ---

    def propose(
        self,
        *,
        action: str,
        action_class: str,
        payload: Any = None,
        source_tier: PrivacyTier | None = None,
        destination_tier: PrivacyTier | None = None,
        destination: str | None = None,
        amount: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> WardenDecision:
        """Propose an action to WARDEN and return its decision. Never executes anything."""
        request = ActionRequest(
            agent=self.name,
            action=action,
            action_class=action_class,
            payload=payload,
            source_tier=source_tier,
            destination_tier=destination_tier,
            destination=destination,
            amount=amount,
            metadata=metadata or {},
        )
        return self.warden.evaluate(request)

    def act(
        self,
        *,
        action: str,
        action_class: str,
        payload: Any = None,
        **kwargs: Any,
    ) -> AgentActionResult:
        """Propose, then execute the bound handler ONLY if WARDEN approves and the agent is active.

        - Not approved (escalate/block): never executes.
        - SHADOW state: proposes and logs, but never executes (shadow mode).
        - ACTIVE state + approved: executes the handler.
        """
        decision = self.propose(action=action, action_class=action_class, payload=payload, **kwargs)

        if not decision.approved:
            return AgentActionResult(decision=decision, executed=False)

        if self.state is OnboardingState.SHADOW:
            return AgentActionResult(decision=decision, executed=False, shadow=True)

        if not self.active:
            # Not yet rolled out: approved in principle, but the agent may not act.
            return AgentActionResult(decision=decision, executed=False)

        handler = self._handlers.get(action)
        if handler is None:
            return AgentActionResult(decision=decision, executed=False)

        output = handler(payload, decision)
        return AgentActionResult(decision=decision, executed=True, output=output)
