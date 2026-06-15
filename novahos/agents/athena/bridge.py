"""ATHENA bridge — read WolfOS life data, propose content goals. Shared across apps. (Agents.)

Reads real signals from WolfOS over the mesh and proposes goal-aligned playbooks. Per the
Constitution, proposals are content_goals rows with status='proposed' — SUGGESTIONS, never
auto-applied. Fail-quiet.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ... import events, suite
from ...models import ContentGoal


def _num(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _behind_target(revenue: dict) -> bool:
    target, current = _num(revenue.get("target")), _num(revenue.get("current"))
    return target > 0 and current < target * 0.9


async def propose_from_life_data(db: AsyncSession, user_id: str, *, account_id: str | None,
                                 account_email: str) -> list[ContentGoal]:
    proposed: list[ContentGoal] = []

    revenue = suite.get_revenue_state(account_email)
    if revenue and _behind_target(revenue):
        proposed.append(ContentGoal(
            user_id=user_id, account_id=account_id, source="wolfos_revenue",
            objective="Drive product sales — revenue is behind target",
            success_metric="leads", playbook_key="sell_product", status="proposed",
            target=_num(revenue.get("target")), current=_num(revenue.get("current")),
        ))

    goals = suite.get_goals(account_email)
    for g in (goals or {}).get("goals", []) if isinstance(goals, dict) else []:
        proposed.append(ContentGoal(
            user_id=user_id, account_id=account_id, source="wolfos_journal",
            wolfos_goal_id=str(g.get("id")) if g.get("id") else None,
            objective=g.get("title", "goal"), success_metric="reach",
            playbook_key="grow_reach", status="proposed",
        ))

    for goal in proposed:
        db.add(goal)
    await db.flush()
    if proposed:
        await events.record(db, user_id, "athena.goals_proposed",
                            {"count": len(proposed), "keys": [g.playbook_key for g in proposed]})
    return proposed
