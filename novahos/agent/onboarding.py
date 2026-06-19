"""The eight-step agent onboarding process (Doc #26 §6).

No agent activates without passing all eight steps, in order:
  1. Manifest validation        — parse and verify the manifest
  2. Constitutional binding      — the Preamble is in the agent's prompt
  3. WARDEN registration         — the agent is registered for action gating
  4. MCP capability check        — declared MCP servers exist and are approved
  5. Sandbox testing             — synthetic actions route through WARDEN
  6. Shadow mode                 — the agent proposes but does not act, for N days
  7. User approval               — the user reviews shadow logs and approves
  8. Gradual rollout             — the agent goes active, green-tier first

Steps 1–5 run automatically. Step 6 (shadow) is entered automatically and exited only once
the shadow period has elapsed. Steps 7–8 are explicit, user-gated transitions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..constitution import preamble_present
from ..warden_runtime.types import ActionRequest
from .base import Agent, OnboardingState
from .manifest import ManifestError, validate_manifest


class OnboardingError(Exception):
    """Raised when an onboarding step fails."""


class OnboardingProcess:
    def __init__(
        self,
        agent: Agent,
        *,
        registry: object | None = None,
        shadow_period: timedelta = timedelta(days=7),
    ) -> None:
        self.agent = agent
        self.registry = registry
        self.shadow_period = shadow_period
        self._shadow_started: datetime | None = None
        self._user_approved = False

    # steps 1–5 + enter shadow (automatic)

    def run_automated(self) -> OnboardingState:
        self._step1_validate_manifest()
        self._step2_bind_constitution()
        self._step3_register_warden()
        self._step4_check_mcp()
        self._step5_sandbox()
        self._enter_shadow()
        return self.agent.state

    def _step1_validate_manifest(self) -> None:
        try:
            validate_manifest(self.agent.manifest.raw)
        except ManifestError as exc:
            raise OnboardingError(f"[{self.agent.name}] manifest invalid: {exc}") from exc
        self.agent.state = OnboardingState.MANIFEST_VALIDATED

    def _step2_bind_constitution(self) -> None:
        if not preamble_present(self.agent.system_prompt):
            raise OnboardingError(f"[{self.agent.name}] Constitutional Preamble not bound.")
        self.agent.state = OnboardingState.CONSTITUTION_BOUND

    def _step3_register_warden(self) -> None:
        if self.agent.warden is None:
            raise OnboardingError(f"[{self.agent.name}] no WARDEN to register with.")
        if self.registry is not None and hasattr(self.registry, "register"):
            self.registry.register(self.agent)
        self.agent.state = OnboardingState.WARDEN_REGISTERED

    def _step4_check_mcp(self) -> None:
        servers = set(self.agent.manifest.reads_from) | set(self.agent.manifest.writes_to)
        boundary = self.agent.mcp_boundary
        if servers and boundary is not None:
            for srv in servers:
                if not boundary.is_approved(srv):
                    raise OnboardingError(
                        f"[{self.agent.name}] declared MCP server '{srv}' is not approved."
                    )
        self.agent.state = OnboardingState.MCP_VERIFIED

    def _step5_sandbox(self) -> None:
        """Run a synthetic action through WARDEN to prove the agent routes through the gate."""
        probe = self.agent.warden.evaluate(
            ActionRequest(
                agent=self.agent.name,
                action="sandbox_probe",
                action_class="read_data",
                metadata={"sandbox": True},
            )
        )
        if probe.audit_entry is None:
            raise OnboardingError(f"[{self.agent.name}] sandbox action was not audited.")
        self.agent.state = OnboardingState.SANDBOX_PASSED

    def _enter_shadow(self, *, now: datetime | None = None) -> None:
        self._shadow_started = now or datetime.now(UTC)
        self.agent.state = OnboardingState.SHADOW

    # steps 6–8 (gated)

    def shadow_elapsed(self, *, now: datetime | None = None) -> bool:
        if self._shadow_started is None:
            return False
        now = now or datetime.now(UTC)
        return now - self._shadow_started >= self.shadow_period

    def approve(self, *, now: datetime | None = None) -> None:
        """Step 7 — the user approves after reviewing shadow logs. Requires shadow elapsed."""
        if self.agent.state is not OnboardingState.SHADOW:
            raise OnboardingError(f"[{self.agent.name}] not in shadow mode; cannot approve.")
        if not self.shadow_elapsed(now=now):
            raise OnboardingError(f"[{self.agent.name}] shadow period not yet elapsed.")
        self._user_approved = True
        self.agent.state = OnboardingState.USER_APPROVED

    def rollout(self) -> None:
        """Step 8 — gradual rollout. The agent goes active (green-tier actions execute)."""
        if not self._user_approved or self.agent.state is not OnboardingState.USER_APPROVED:
            raise OnboardingError(f"[{self.agent.name}] cannot roll out before user approval.")
        self.agent.state = OnboardingState.ACTIVE
