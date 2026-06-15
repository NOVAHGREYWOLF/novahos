"""WARDEN gate (DB-persisting) — the full numeric-API gate apps call. (Substrate.)

Wraps the pure stdlib decision (novahos.warden) with consent resolution, hard validators, and
persistence of the risk score + immutable audit entry. Returns a warden.GateDecision; PUBLISHER
acts only when `decision.may_execute`.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from . import consent, validators, warden, warden_audit


async def evaluate(
    db: AsyncSession,
    user_id: str,
    *,
    agent: str,
    account_id: str | None,
    account_consent_tiers: dict | None,
    auto_post_threshold: int,
    subject_type: str,
    subject_id: str | None,
    risk_ctx: warden.RiskContext,
    validation_ctx: validators.ValidationContext,
) -> warden.GateDecision:
    tier = consent.tier_for(risk_ctx.action_type, account_consent_tiers)
    violations = validators.validate(validation_ctx)
    risk = warden.score_action(risk_ctx)
    d = warden.decide(risk=risk, tier=tier, threshold=auto_post_threshold, hard_violations=violations)

    inputs = {"breakdown": risk.parts, "flags": risk.flags, "violations": violations,
              "tier": tier, "compliance_mode": risk_ctx.compliance_mode}
    await warden_audit.write_risk_score(
        db, user_id, account_id=account_id, subject_type=subject_type, subject_id=subject_id,
        inputs=inputs, score=d.score, decision=d.decision, threshold=auto_post_threshold,
    )
    await warden_audit.write(
        db, user_id, agent=agent, action=risk_ctx.action_type,
        constitution_result=d.constitution_result, consent_tier=tier,
        risk_score=d.score, decision=d.decision, detail=inputs,
    )
    return d
