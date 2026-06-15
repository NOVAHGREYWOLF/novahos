"""DM-FUNNEL — the 24h-window comment/DM funnel state machine. Compliant by construction. (Agents.)

Standard DMs only inside the 24h window opened by user-initiated contact. State:
  new → engaged → qualified → cta_sent → converted   (or → expired)
Outbound replies still pass through WARDEN (send_dm is RED). This owns STATE.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ... import events
from ...models import DmFlow, DmMessage

WINDOW = timedelta(hours=24)
_NEXT = {"new": "engaged", "engaged": "qualified", "qualified": "cta_sent", "cta_sent": "converted"}


async def on_inbound(db: AsyncSession, user_id: str, *, account_id: str, thread_id: str,
                     contact_id: str, text: str, flow_key: str | None = None,
                     now: datetime | None = None) -> DmFlow:
    now = now or datetime.now(timezone.utc)
    flow = (await db.execute(
        select(DmFlow).where(DmFlow.account_id == account_id, DmFlow.thread_id == thread_id)
    )).scalar_one_or_none()
    if flow is None:
        flow = DmFlow(user_id=user_id, account_id=account_id, thread_id=thread_id,
                      contact_id=contact_id, flow_key=flow_key, state="engaged")
        db.add(flow)
    elif flow.state in ("new", "expired"):
        flow.state = "engaged"
    flow.last_inbound_at = now
    flow.window_expires_at = now + WINDOW
    await db.flush()
    db.add(DmMessage(user_id=user_id, flow_id=flow.id, direction="inbound", text=text, ts=now))
    await events.record(db, user_id, "dm.inbound", {"flow_id": flow.id, "state": flow.state})
    await db.flush()
    return flow


def window_open(flow: DmFlow, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return flow.window_expires_at is not None and flow.window_expires_at >= now


async def on_outbound(db: AsyncSession, user_id: str, *, flow: DmFlow, text: str,
                      advance: bool = True, now: datetime | None = None) -> DmFlow:
    now = now or datetime.now(timezone.utc)
    flow.last_outbound_at = now
    if advance:
        flow.state = _NEXT.get(flow.state, flow.state)
    db.add(DmMessage(user_id=user_id, flow_id=flow.id, direction="outbound", text=text, ts=now))
    await events.record(db, user_id, "dm.outbound", {"flow_id": flow.id, "state": flow.state})
    await db.flush()
    return flow


async def expire_stale(db: AsyncSession, user_id: str, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    flows = (await db.execute(
        select(DmFlow).where(DmFlow.state.notin_(["converted", "expired"]))
    )).scalars().all()
    n = 0
    for f in flows:
        if not window_open(f, now):
            f.state = "expired"
            n += 1
    await db.flush()
    return n
