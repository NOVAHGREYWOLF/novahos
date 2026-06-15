"""CHRONICLE (APOLLO) — shared capture/log agent. Context-driven. (Agents.)

Creates the content_pieces row for whatever app/channel the context names and records a
`content.captured` event. The same agent serves Instagram, LinkedIn, email.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ... import events
from ...context import AgentContext
from ...models import ContentPiece


async def capture(
    db: AsyncSession,
    ctx: AgentContext,
    *,
    source: str = "watched_folder",
    goal_id: str | None = None,
    meta: dict | None = None,
) -> ContentPiece:
    piece = ContentPiece(
        user_id=ctx.user_id, account_id=getattr(ctx.account, "id", None),
        app=ctx.app, channel=ctx.channel, source=source,
        playbook_key=ctx.playbook_key, goal_id=goal_id, status="new", meta=meta or {},
    )
    db.add(piece)
    await db.flush()
    await events.record(db, ctx.user_id, "content.captured",
                        {"content_piece_id": piece.id, "app": ctx.app,
                         "channel": ctx.channel, "source": source}, channel=ctx.channel)
    return piece
