"""The runtime WARDEN gate — deterministic, NO LLM. Agents propose; WARDEN disposes. (Foundation.)

Every agent action routes through `Warden.evaluate()` before execution: the six validators run
in fixed order, the strictest verdict wins, and one entry is written to the hash-chained
`novahos.audit_trail.AuditTrail` (step 7) before the decision returns. WARDEN can block, force
escalation, throttle, and suspend agents — it cannot override the user or self-modify.

Ported from the NovahPrime foundation; rewired onto `novahos.audit_trail`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..audit_trail import AuditEntry, AuditTrail
from .types import (
    ActionRequest,
    AuthTier,
    Decision,
    ValidatorResult,
    Validator,
    WardenContext,
)
from .validators import default_validators


@dataclass(frozen=True)
class WardenDecision:
    """The final verdict for one action request, with full reasoning and its audit entry."""

    decision: Decision
    request: ActionRequest
    reasons: tuple[str, ...]
    validator_results: tuple[ValidatorResult, ...]
    audit_entry: AuditEntry
    required_auth_tier: AuthTier | None = None

    @property
    def approved(self) -> bool:
        return self.decision is Decision.APPROVE

    @property
    def escalated(self) -> bool:
        return self.decision is Decision.ESCALATE

    @property
    def blocked(self) -> bool:
        return self.decision is Decision.BLOCK

    @property
    def verdict(self) -> str:
        """Lowercase verdict string, identical to novahos.warden (approve/escalate/block)."""
        return self.decision.verdict


class Warden:
    """The deterministic gate. Construct once (see novahos.warden_runtime.build_warden); call
    `evaluate` for every action."""

    def __init__(
        self,
        *,
        audit_trail: AuditTrail,
        consent,
        auth,
        safety,
        resources,
        conflicts,
        privacy,
        classifier=None,
        validators: list[Validator] | None = None,
    ) -> None:
        self._audit = audit_trail
        self._consent = consent
        self._auth = auth
        self._safety = safety
        self._resources = resources
        self._conflicts = conflicts
        self._privacy = privacy
        self._classifier = classifier
        self._validators = validators if validators is not None else default_validators()
        self._suspended: set[str] = set()

    @property
    def audit_trail(self) -> AuditTrail:
        return self._audit

    @property
    def check_sequence(self) -> tuple[str, ...]:
        return tuple(v.name for v in self._validators)

    # --- authority: throttle / suspend (cannot override user or self-modify) ---

    def suspend_agent(self, agent: str) -> None:
        self._suspended.add(agent)

    def reinstate_agent(self, agent: str) -> None:
        self._suspended.discard(agent)

    def is_suspended(self, agent: str) -> bool:
        return agent in self._suspended

    # --- the gate ---

    def evaluate(self, request: ActionRequest) -> WardenDecision:
        """Run the full sequence and return the decision. Every call is audited."""
        if request.agent in self._suspended:
            return self._finalize(
                request, Decision.BLOCK,
                [ValidatorResult("suspension", Decision.BLOCK, (f"Agent '{request.agent}' is suspended.",))],
                None)

        ctx = WardenContext(
            request=request, consent=self._consent, auth=self._auth, safety=self._safety,
            resources=self._resources, conflicts_registry=self._conflicts, privacy=self._privacy,
            classifier=self._classifier)

        results: list[ValidatorResult] = [v.check(ctx) for v in self._validators]
        decision = max((r.decision for r in results), default=Decision.APPROVE)
        required_auth = self._max_required_auth(results)

        # Only an approved action consumes budget and claims resources.
        if decision is Decision.APPROVE:
            self._resources.commit(request)
            self._conflicts.register(request)

        return self._finalize(request, decision, results, required_auth)

    # --- helpers ---

    @staticmethod
    def _max_required_auth(results: list[ValidatorResult]) -> AuthTier | None:
        tiers = [r.required_auth_tier for r in results if r.required_auth_tier is not None]
        return max(tiers) if tiers else None

    def _finalize(self, request, decision, results, required_auth) -> WardenDecision:
        reasons: list[str] = []
        for r in results:
            reasons.extend(r.reasons)
        entry = self._audit.record(  # step 7: audit every decision before returning
            trace_id=request.trace_id, agent=request.agent, action=request.action,
            action_class=request.action_class, decision=decision.name, reasons=reasons,
            payload=request.payload,
            metadata={
                "required_auth_tier": required_auth.name if required_auth else None,
                "destination": request.destination,
                "amount": request.amount,
                "checks": [{"name": r.name, "decision": r.decision.name} for r in results],
            })
        return WardenDecision(
            decision=decision, request=request, reasons=tuple(reasons),
            validator_results=tuple(results), audit_entry=entry, required_auth_tier=required_auth)
