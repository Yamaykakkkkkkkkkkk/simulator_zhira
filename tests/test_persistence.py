import os
import tempfile
from datetime import timedelta

import pytest

from sqlalchemy import select

from fatbot import data, services
from fatbot.db import init_db, make_engine, make_sessionmaker, migrate_db
from fatbot.models import Farm, User, UserQuest
from fatbot.utils import utcnow


def _db_path():
    d = tempfile.mkdtemp(prefix="fatpersist_")
    return f"sqlite+aiosqlite:///{os.path.join(d, 'test.db').replace(os.sep, '/')}"


async def _boot(url):
    """Имитация запуска бота: новый engine + миграции (как в bot.py)."""
    engine = make_engine(url)
    await init_db(engine)
    await migrate_db(engine)
    return engine, make_sessionmaker(engine)


@pytest.mark.asyncio
async def test_farm_survives_restart():
    """Столовая игрока НЕ должна исчезать при перезапуске бота (регресс на DROP TABLE farms)."""
    url = _db_path()
    engine, sm = await _boot(url)
    async with sm() as s:
        u = await services.get_or_create_user(s, 1, "u", "U")
        u.points = 10 ** 9
        await s.flush()
        farm, err = await services.create_farm(s, u.id, 500_000)
        assert err is None
        await services.place_food_in_slot(s, farm, 1, "cake")
        farm.is_running = True
        await s.commit()
        farm_id = farm.id
    await engine.dispose()

    # перезапуск бота
    engine2, sm2 = await _boot(url)
    try:
        async with sm2() as s:
            farm2 = await services.get_farm(s, 1)
            assert farm2 is not None, "столовая пропала после перезапуска бота"
            assert farm2.id == farm_id
            assert farm2.level == 1
            assert farm2.slot1_product == "cake", "продукт в слоте потерян"
            assert farm2.is_running is True
            u = await s.get(User, 1)
            # 500_000 за столовую + цена блюда в слоте
            expected = 10 ** 9 - 500_000 - data.FARM_PRODUCTS_BY_KEY["cake"]["price"]
            assert u.points == expected, f"баланс изменился: {u.points} != {expected}"
    finally:
        await engine2.dispose()


@pytest.mark.asyncio
async def test_farm_rows_of_other_users_not_touched():
    """DROP в старой миграции сносил столовые ВСЕХ игроков сразу."""
    url = _db_path()
    engine, sm = await _boot(url)
    async with sm() as s:
        for uid in (1, 2, 3):
            u = await services.get_or_create_user(s, uid, f"u{uid}", "U")
            u.points = 10 ** 9
            await s.flush()
            await services.create_farm(s, uid, 500_000)
        await s.commit()
    await engine.dispose()

    engine2, sm2 = await _boot(url)
    try:
        async with sm2() as s:
            for uid in (1, 2, 3):
                assert await services.get_farm(s, uid) is not None, f"столовая uid={uid} пропала"
    finally:
        await engine2.dispose()


@pytest.mark.asyncio
async def test_daily_quest_resets_after_reset_at():
    """Ежедневный квест должен сбрасываться после reset_at, а не навсегда оставаться выполненным."""
    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 1, "u", "U")
            await s.flush()
            await services.update_quest_progress(s, u.id, "open5", 10)
            q = await services.get_quest_progress(s, u.id, "open5")
            assert q is not None and q.completed

            # наступил новый день
            q.reset_at = utcnow() - timedelta(seconds=1)
            await s.flush()

            await services.update_quest_progress(s, u.id, "open5", 1)
            q2 = await services.get_quest_progress(s, u.id, "open5")
            assert q2.progress == 1, f"прогресс не сбросился: {q2.progress} (reset_at игнорируется)"
            assert q2.completed is False
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_quest_row_recreated_after_reset():
    """После сброса квест должен снова давать награду."""
    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 1, "u", "U")
            await s.flush()
            await services.update_quest_progress(s, u.id, "open5", 10)
            first = await services.claim_quest(s, u.id, "open5")
            assert first is not None

            q = await services.get_quest_progress(s, u.id, "open5")
            q.reset_at = utcnow() - timedelta(seconds=1)
            await s.flush()

            await services.update_quest_progress(s, u.id, "open5", 10)
            second = await services.claim_quest(s, u.id, "open5")
            assert second is not None, "после сброса награда снова недоступна"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_weekly_quest_resets_too():
    """Еженедельные квесты тоже должны сбрасываться по reset_at."""
    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 1, "u", "U")
            await s.flush()
            await services.update_quest_progress(s, u.id, "open50", 999)
            q = await services.get_quest_progress(s, u.id, "open50")
            assert q is not None
            q.reset_at = utcnow() - timedelta(seconds=1)
            await s.flush()
            await services.update_quest_progress(s, u.id, "open50", 1)
            q2 = await services.get_quest_progress(s, u.id, "open50")
            assert q2.progress == 1, "еженедельный квест не сбросился"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_progress_outside_rotation_is_visible():
    """Прогресс по квесту, НЕ попавшему в ротацию, обязан быть виден игроку.

    Хендлеры засчитывают фиксированные ключи (open5, sell3...), а ротация показывает
    3 случайных квеста из 12 — без этой правки игрок делал действие и не видел ничего.
    """
    from fatbot.handlers import quests as qh

    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 42, "u", "U")
            await s.flush()
            rotation = {q["key"] for q in services.get_user_daily_quests(u.id)}
            # квест, которого НЕТ в ротации этого игрока
            outside = next(q for q in data.DAILY_QUESTS if q["key"] not in rotation)
            await services.update_quest_progress(s, u.id, outside["key"], 1)

            shown = await qh._daily_with_progress(s, u)
            keys = {q["key"] for q in shown}
            assert outside["key"] in keys, (
                f"квест {outside['key']} с прогрессом не показан игроку "
                f"(ротация={sorted(rotation)})"
            )
            assert rotation <= keys, "ротационные квесты должны остаться в списке"

            # и кнопка для забора награды тоже должна быть
            btn_keys = await qh._active_keys_full(s, u)
            assert outside["key"] in btn_keys
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_rotation_quests_still_visible_without_progress():
    """Ротация показывается всегда, даже если по ним нет прогресса."""
    from fatbot.handlers import quests as qh

    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 7, "u", "U")
            await s.flush()
            shown = await qh._daily_with_progress(s, u)
            rotation = {q["key"] for q in services.get_user_daily_quests(u.id)}
            assert rotation <= {q["key"] for q in shown}
            assert len(shown) == 3
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_purge_stale_quests_keeps_fresh_rows():
    """Чистка не должна трогать актуальные квесты."""
    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 1, "u", "U")
            await s.flush()
            await services.update_quest_progress(s, u.id, "open5", 1)
            await services.update_quest_progress(s, u.id, "sell3", 1)
            removed = await services.purge_stale_quests(s, keep_days=7)
            assert removed == 0
            assert (await services.get_quest_progress(s, u.id, "open5")).progress == 1
            assert (await services.get_quest_progress(s, u.id, "sell3")).progress == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_stale_quest_rows_are_cleaned():
    """Сильно протухшие строки квестов не должны копиться вечно."""
    url = _db_path()
    engine, sm = await _boot(url)
    try:
        async with sm() as s:
            u = await services.get_or_create_user(s, 1, "u", "U")
            await s.flush()
            await services.update_quest_progress(s, u.id, "open5", 1)
            q = await services.get_quest_progress(s, u.id, "open5")
            q.reset_at = utcnow() - timedelta(days=30)
            await s.flush()
            await services.update_quest_progress(s, u.id, "sell3", 1)
        async with sm() as s:
            rows = (await s.execute(select(UserQuest))).scalars().all()
            stale = [r for r in rows if r.reset_at < utcnow() - timedelta(days=7)]
            assert not stale, f"остались протухшие строки квестов: {len(stale)}"
    finally:
        await engine.dispose()
