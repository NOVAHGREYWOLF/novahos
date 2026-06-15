"""PUBLISHER (APOLLO) — shared publisher. Channel-agnostic, context-driven. (Agents.)

Resolves a ChannelBackend from the context via the registry (so the SAME PUBLISHER posts to
Instagram, LinkedIn, …) and acts only after WARDEN returns auto_post (the pipeline enforces that).
Records the posts row with the bandit suggestion_id for reward attribution.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ... import events
from ...channels import registry
from ...channels.base import MediaRef
from ...context import AgentContext
from ...models import ContentDraft, MediaAsset, Post


def assemble_body(draft: ContentDraft) -> str:
    parts = [draft.body or ""]
    if draft.cta:
        parts.append(draft.cta)
    if draft.tags:
        parts.append(" ".join(draft.tags))
    return "\n\n".join(p for p in parts if p)


async def publish(
    db: AsyncSession,
    ctx: AgentContext,
    *,
    draft: ContentDraft,
    media: MediaAsset | None,
    kind: str = "reel",
    public_url: str | None = None,
) -> Post:
    backend = registry.resolve(ctx)
    acc_ref = registry.account_ref(ctx.account, ctx.channel)
    media_ref = MediaRef(kind=kind, path=getattr(media, "path", None), url=public_url,
                         duration_s=getattr(media, "duration_s", None))
    body = assemble_body(draft)

    result = await backend.publish(acc_ref, media_ref, body, kind=kind)

    post = Post(
        user_id=ctx.user_id, account_id=ctx.account.id, content_piece_id=draft.content_piece_id,
        draft_id=draft.id, channel=ctx.channel, platform_post_id=result.platform_post_id,
        permalink=result.permalink, kind=kind, backend_mode=ctx.compliance_mode,
        raw={"status": result.status, "warnings": result.warnings,
             "suggestion_id": draft.suggestion_id, **result.raw},
    )
    db.add(post)
    await db.flush()
    await events.record(db, ctx.user_id, "content.posted",
                        {"post_id": post.id, "status": result.status, "channel": ctx.channel,
                         "mode": ctx.compliance_mode, "warnings": result.warnings}, channel=ctx.channel)
    return post
