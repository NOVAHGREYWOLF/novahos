"""The six WARDEN check steps, in canonical order. (Foundation; stdlib, NO LLM.)

Ported from the NovahPrime foundation. Each validator is pure: it inspects the WardenContext
and returns a ValidatorResult. The engine runs them in order and takes the strictest verdict.
"""
from __future__ import annotations

from .types import (
    AuthTier,
    ConsentTier,
    ConstitutionalCheck,
    Decision,
    PrivacyTier,
    ValidatorResult,
    WardenContext,
)


class ConstitutionalValidator:
    """Step 1 — autonomy / safety / goals. Override attempts BLOCK; autonomy/safety gaps ESCALATE."""

    name = "constitutional"

    def check(self, ctx: WardenContext) -> ValidatorResult:
        req = ctx.request
        if req.metadata.get("override_constitution"):
            return ValidatorResult(
                self.name, Decision.BLOCK,
                ("Action attempts to override the Constitution; no agent may do so.",))

        autonomy_ok = ctx.consent.is_authorized(req.action_class)
        safety_ok, safety_detail = ctx.safety.assess(req)
        check = ConstitutionalCheck(autonomy_ok=autonomy_ok, safety_ok=safety_ok,
                                    goals_ok=True, detail=safety_detail)
        if check.passed:
            return ValidatorResult(self.name, Decision.APPROVE)

        reasons: list[str] = []
        if not autonomy_ok:
            reasons.append(f"Autonomy: action class '{req.action_class}' is not authorized by the user.")
        if not safety_ok:
            reasons.append(f"Safety: potential harm — {safety_detail or 'flagged for user confirmation'}.")
        if check.violated_principle is not None:
            reasons.append(f"Highest-priority principle in tension: {check.violated_principle.title}.")
        return ValidatorResult(self.name, Decision.ESCALATE, tuple(reasons))


class ConsentTierValidator:
    """Step 2 — green acts; yellow proposes; red escalates + needs re-auth; unknown escalates."""

    name = "consent_tier"

    def check(self, ctx: WardenContext) -> ValidatorResult:
        tier = ctx.consent.consent_tier(ctx.request.action_class)
        if tier is ConsentTier.GREEN:
            return ValidatorResult(self.name, Decision.APPROVE, ("Consent: GREEN (pre-authorized).",))
        if tier is ConsentTier.YELLOW:
            return ValidatorResult(self.name, Decision.ESCALATE,
                                   ("Consent: YELLOW — propose and await approval.",))
        if tier is ConsentTier.RED:
            return ValidatorResult(self.name, Decision.ESCALATE,
                                   ("Consent: RED — real-time approval plus re-authentication required.",),
                                   required_auth_tier=AuthTier.HIGH_VALUE)
        return ValidatorResult(self.name, Decision.ESCALATE,
                               (f"Consent: action class '{ctx.request.action_class}' has no assigned tier; escalating.",))


class AuthStateValidator:
    """Step 3 — session auth tier must meet the action's required tier; CATASTROPHIC needs cooling."""

    name = "auth_state"

    def check(self, ctx: WardenContext) -> ValidatorResult:
        required = ctx.auth.required_tier(ctx.request.action_class)
        current = ctx.auth.current_tier()
        if current < required:
            return ValidatorResult(
                self.name, Decision.ESCALATE,
                (f"Auth: requires {required.name} but session is at {current.name}; re-authentication required.",),
                required_auth_tier=required)
        if required is AuthTier.CATASTROPHIC and not ctx.auth.cooling_satisfied(ctx.request):
            return ValidatorResult(
                self.name, Decision.ESCALATE,
                ("Auth: CATASTROPHIC action requires the cooling delay to elapse before execution.",),
                required_auth_tier=AuthTier.CATASTROPHIC)
        return ValidatorResult(self.name, Decision.APPROVE)


class ResourceLimitValidator:
    """Step 4 — rate / spending / throughput. Exceeding a hard cap BLOCKS (throttle a runaway)."""

    name = "resource_limits"

    def check(self, ctx: WardenContext) -> ValidatorResult:
        ok, reasons = ctx.resources.check(ctx.request)
        if ok:
            return ValidatorResult(self.name, Decision.APPROVE)
        return ValidatorResult(self.name, Decision.BLOCK, tuple(reasons))


class CrossAgentConflictValidator:
    """Step 5 — two agents writing the same resource conflict → ESCALATE (don't last-writer-win)."""

    name = "cross_agent_conflict"

    def check(self, ctx: WardenContext) -> ValidatorResult:
        conflicts = ctx.conflicts_registry.conflicts(ctx.request)
        if not conflicts:
            return ValidatorResult(self.name, Decision.APPROVE)
        return ValidatorResult(self.name, Decision.ESCALATE,
                               tuple(f"Cross-agent conflict on resource with: {c}" for c in conflicts))


class PrivacyTierTransitionValidator:
    """Step 6 — fail-closed cloud-leak guard. Tier-1→cloud BLOCK; unknown→cloud BLOCK; downgrade ESCALATE."""

    name = "privacy_tier_transition"

    def _effective_source(self, ctx: WardenContext) -> PrivacyTier | None:
        req = ctx.request
        if req.source_tier is not None:
            return req.source_tier
        data_type = req.metadata.get("data_type")
        if data_type and ctx.classifier is not None:
            return ctx.classifier.classify(str(data_type))
        return None

    def check(self, ctx: WardenContext) -> ValidatorResult:
        req = ctx.request
        is_cloud = ctx.privacy.is_cloud_destination(req)
        source = self._effective_source(ctx)
        dest = req.destination_tier
        if is_cloud:
            if source is PrivacyTier.TIER_1:
                return ValidatorResult(self.name, Decision.BLOCK,
                                       ("Privacy: Tier 1 (PRIVATE) data may never be sent to a cloud/external destination.",))
            if source is None:
                return ValidatorResult(self.name, Decision.BLOCK,
                                       ("Privacy: cannot send to an external destination without a declared/derivable "
                                        "non-private data tier (failing closed).",))
        if source is not None and dest is not None and dest.value > source.value:
            return ValidatorResult(self.name, Decision.ESCALATE,
                                   (f"Privacy: downgrade {source.name} -> {dest.name} requires an explicit consent gate.",))
        return ValidatorResult(self.name, Decision.APPROVE)


def default_validators() -> list:
    """The six validators in their canonical, non-negotiable order."""
    return [
        ConstitutionalValidator(),
        ConsentTierValidator(),
        AuthStateValidator(),
        ResourceLimitValidator(),
        CrossAgentConflictValidator(),
        PrivacyTierTransitionValidator(),
    ]
