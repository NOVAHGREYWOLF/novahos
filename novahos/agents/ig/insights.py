"""INSIGHTS — pull metrics, compute the goal-attributed reward, feed the bandit. Context-driven. (Agents.)

read_insights via the channel backend → persist insights → goal_outcome from the playbook's
success_metric → record_outcome on the per-channel+account+goal bandit policy.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ... import content_learning, learning
from ...channels import registry
from ...context import AgentContext
from ...models import Insight, Post


async def sync_post(db: AsyncSession, ctx: AgentContext, *, post: Post,
                    success_metric: str, objective: str, baseline_reach: float = 1.0) -> Insight:
    backend = registry.resolve(ctx)
    acc_ref = registry.account_ref(ctx.account, ctx.channel)
    rows = await backend.read_insights(acc_ref, [post.platform_post_id]) if post.platform_post_id else []

    row = rows[0] if rows else None
    ins = Insight(
        user_id=ctx.user_id, post_id=post.id, platform_post_id=post.platform_post_id,
        reach=getattr(row, "reach", 0), impressions=getattr(row, "impressions", 0),
        likes=getattr(row, "likes", 0), comments=getattr(row, "comments", 0),
        saves=getattr(row, "saves", 0), shares=getattr(row, "shares", 0),
        plays=getattr(row, "plays", 0), profile_visits=getattr(row, "profile_visits", 0),
        follows=getattr(row, "follows", 0), link_clicks=getattr(row, "link_clicks", 0),
        raw=getattr(row, "raw", {}) or {},
    )
    ins.goal_outcome = content_learning.goal_outcome_from_insight(ins, success_metric, baseline_reach)
    db.add(ins)
    await db.flush()

    suggestion_id = (post.raw or {}).get("suggestion_id")
    if suggestion_id:
        await learning.record_outcome(
            db, ctx.user_id, suggestion_id, float(ins.goal_outcome or 0.0),
            policy_key=content_learning.policy_key(ctx.channel, ctx.account.id, objective),
        )
    return ins


async def sync_recent(db: AsyncSession, ctx: AgentContext, *, success_metric: str,
                      objective: str, limit: int = 25) -> int:
    posts = (await db.execute(
        select(Post).where(Post.account_id == ctx.account.id)
        .order_by(Post.posted_at.desc()).limit(limit)
    )).scalars().all()
    for p in posts:
        await sync_post(db, ctx, post=p, success_metric=success_metric, objective=objective)
    return len(posts)
