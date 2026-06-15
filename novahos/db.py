"""Async DB engine + session. Multi-tenant RLS per request, NOVAH's own schema. (Substrate.)"""
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings


def _async_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if "+asyncpg" in url and "?" in url:
        url = url.split("?", 1)[0]
    return url


engine = create_async_engine(
    _async_url(settings.database_url),
    pool_pre_ping=True,
    connect_args={"server_settings": {"search_path": f"{settings.db_schema}, public"}},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def session_for_user(user_id: str) -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": user_id})
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def session_unscoped() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
