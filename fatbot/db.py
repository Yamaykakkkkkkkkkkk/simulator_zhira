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


async def _add_missing_columns(engine, table: str, cols: dict[str, str]) -> None:
    """Неразрушающая миграция: добавить недостающие колонки, НЕ трогая существующие данные.

    Раньше здесь стоял `DROP TABLE IF EXISTS farms`, который сносил столовые ВСЕХ игроков
    при каждом старте бота. Теперь таблица только дополняется.
    """
    if not cols:
        return
    async with engine.begin() as conn:
        try:
            if "sqlite" in str(engine.url):
                existing = {
                    c[1] for c in (await conn.execute(text(f"PRAGMA table_info({table})"))).all()
                }
                for col, sqltype in cols.items():
                    if col not in existing:
                        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {sqltype}"))
            elif "postgresql" in str(engine.url):
                for col, sqltype in cols.items():
                    await conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {sqltype}")
                    )
        except Exception:
            pass


# колонки farms, которых могло не быть в старых базах (добавлены вместе с ростом кухни)
_FARM_COLUMNS = {
    "level": "INTEGER DEFAULT 1",
    "slot1_product": "VARCHAR(32)",
    "slot2_product": "VARCHAR(32)",
    "slot3_product": "VARCHAR(32)",
    "slot4_product": "VARCHAR(32)",
    "slot5_product": "VARCHAR(32)",
    "slot6_product": "VARCHAR(32)",
    "total_calories": "INTEGER DEFAULT 0",
    "is_running": "BOOLEAN DEFAULT 0",
    "last_collect": "TIMESTAMP",
    "created_at": "TIMESTAMP",
}

_USER_COLUMNS = {
    "collector_lvl": "INTEGER DEFAULT 0",
    "auctioneer_lvl": "INTEGER DEFAULT 0",
    "gambler_lvl": "INTEGER DEFAULT 0",
    "chef_lvl": "INTEGER DEFAULT 0",
    "keeper_lvl": "INTEGER DEFAULT 0",
    "prestige_lvl": "INTEGER DEFAULT 0",
    "story_step": "INTEGER DEFAULT 0",
}


async def migrate_db(engine):
    # farms: создать если нет (init_db уже сделал create_all) и ДОПОЛНИТЬ недостающие колонки
    async with engine.begin() as conn:
        await conn.run_sync(models.Farm.__table__.create, checkfirst=True)
    await _add_missing_columns(engine, "farms", _FARM_COLUMNS)
    await _add_missing_columns(engine, "users", _USER_COLUMNS)


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
