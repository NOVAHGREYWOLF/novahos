"""Event-log service — the one way state changes are recorded (the spine). (Substrate.)"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Event


async def record(db: AsyncSession, user_id: str, type_: str, payload: dict, channel: str | None = None) -> Event:
    ev = Event(user_id=user_id, type=type_, payload=payload, channel=channel)
    db.add(ev)
    await db.flush()
    return ev


async def recent(db: AsyncSession, user_id: str, limit: int = 20) -> list[Event]:
    rows = await db.execute(
        select(Event).where(Event.user_id == user_id).order_by(Event.ts.desc()).limit(limit)
    )
    return list(rows.scalars().all())
