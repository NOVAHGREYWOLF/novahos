"""Immutable audit writer for WARDEN decisions. (Substrate — needs the DB.)

`warden_audit_trail` revokes UPDATE/DELETE at the DB layer, so this only appends. The pure
decision functions live in novahos.warden (stdlib); this persists their results.

BOTH WRITERS BELOW REDACT FIRST, AND THE APPEND-ONLY GUARANTEE IS WHY
─────────────────────────────────────────────────────────────────────
`detail` and `inputs` are caller-supplied dicts that went into the database exactly as
handed over. Append-only is the right design for an audit trail and it is also what makes
an unredacted write unrecoverable: a token in `warden_audit_trail` cannot be edited out
afterwards, because the table revokes the statement that would do it. It can only be
dropped with the table.

Odyssey already had this protection — `_safe_payload_summary` in its private WARDEN fork —
and the kernel did not, so it existed in the one repository that had built its own way
around the kernel and was absent from every service using the kernel as intended. See
novahos/redaction.py.

`audit_trail.py` is deliberately untouched: it stores `payload_digest`, a SHA-256 over the
canonical JSON, so no plaintext has ever reached it. Adding redaction there would be
hardening the writer that was already safe.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from .models import RiskScore, WardenAudit
from .redaction import safe_payload


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
        risk_score=risk_score, decision=decision, detail=safe_payload(detail),
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
        subject_id=subject_id, inputs=safe_payload(inputs), score=score, decision=decision,
        threshold=threshold,
    )
    db.add(row)
    await db.flush()
    return row
