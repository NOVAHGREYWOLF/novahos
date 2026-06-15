"""Immutable audit writer for WARDEN decisions. (Substrate — needs the DB.)

`warden_audit_trail` revokes UPDATE/DELETE at the DB layer, so this only appends. The pure
decision functions live in novahos.warden (stdlib); this persists their results.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RiskScore, WardenAudit


async def write(
    db: AsyncSession,
    user_id: str,
    *,
    agent: str,
    action: str,
    constitution_result: str,
    consent_tier: str,
    risk_score: int,
    decision: str,
    detail: dict,
) -> None:
    db.add(WardenAudit(
        user_id=user_id, agent=agent, action=action,
        constitution_result=constitution_result, consent_tier=consent_tier,
        risk_score=risk_score, decision=decision, detail=detail,
    ))
    await db.flush()


async def write_risk_score(
    db: AsyncSession,
    user_id: str,
    *,
    account_id: str | None,
    subject_type: str,
    subject_id: str | None,
    inputs: dict,
    score: int,
    decision: str,
    threshold: int,
) -> RiskScore:
    row = RiskScore(
        user_id=user_id, account_id=account_id, subject_type=subject_type,
        subject_id=subject_id, inputs=inputs, score=score, decision=decision, threshold=threshold,
    )
    db.add(row)
    await db.flush()
    return row
