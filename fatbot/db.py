from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from . import models


def make_engine(url: str):
    kwargs = {}
    if url.startswith("sqlite") and ":memory:" in url:
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool
    return create_async_engine(url, **kwargs)


async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


async def migrate_db(engine):
    async with engine.begin() as conn:
        if "postgresql" in str(engine.url):
            await conn.execute(text("""
                ALTER TABLE farms
                ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1
            """))
        elif "sqlite" in str(engine.url):
            try:
                await conn.execute(text("ALTER TABLE farms ADD COLUMN level INTEGER DEFAULT 1"))
            except Exception:
                pass


def make_sessionmaker(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


class DbSessionMiddleware:
    def __init__(self, sessionmaker=None):
        self.sm = sessionmaker

    async def __call__(self, handler, event, data):
        sm = data.get("sessionmaker") or self.sm
        async with sm() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
