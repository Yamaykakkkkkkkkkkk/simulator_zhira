import random
from datetime import datetime

import pytest

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, Message as TgMessage, Update, User as TgUser

from fatbot.db import DbSessionMiddleware, init_db, make_engine, make_sessionmaker
from fatbot.handlers import build_router
from fatbot.handlers.trade import TRADES
from fatbot.handlers.market import PENDING_PRICE
from fatbot.models import User, UserCard
from fatbot.utils import utcnow


_DP = Dispatcher(storage=MemoryStorage())
_DP.update.outer_middleware(DbSessionMiddleware())
_DP.include_router(build_router())


class RecordingBot(Bot):
    def __init__(self):
        super().__init__(token="42:TEST")
        self.calls = []

    async def __call__(self, method, request_timeout=None):
        self.calls.append(method)
        if isinstance(method, (SendMessage, SendPhoto)):
            return TgMessage(
                message_id=len(self.calls),
                date=datetime.now(),
                chat=Chat(id=getattr(method, "chat_id"), type="private"),
            )
        return True

    def texts(self):
        out = []
        for c in self.calls:
            if isinstance(c, SendMessage):
                out.append(c.text or "")
            elif isinstance(c, SendPhoto):
                out.append(c.caption or "")
            elif hasattr(c, "text") and isinstance(getattr(c, "text", None), str):
                out.append(c.text)
        return out


@pytest.fixture()
async def env():
    engine = make_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    sm = make_sessionmaker(engine)
    bot = RecordingBot()
    TRADES.clear()
    PENDING_PRICE.clear()

    class Ctx:
        pass

    ctx = Ctx()
    ctx.engine, ctx.sm, ctx.dp, ctx.bot = engine, sm, _DP, bot
    ctx.uid = iter(range(1000, 100000))

    async def send(text, user_id=1, username="u1", reply_to=None):
        u = TgUser(id=user_id, is_bot=False, first_name="U", username=username)
        msg = TgMessage(
            message_id=next(ctx.uid),
            date=datetime.now(),
            chat=Chat(id=user_id, type="private"),
            from_user=u,
            text=text,
        )
        await _DP.feed_update(bot, Update(update_id=next(ctx.uid), message=msg), sessionmaker=sm)

    async def tap(data, user_id=1, username="u1"):
        u = TgUser(id=user_id, is_bot=False, first_name="U", username=username)
        holder = TgMessage(
            message_id=next(ctx.uid), date=datetime.now(), chat=Chat(id=user_id, type="private")
        )
        cq = CallbackQuery(
            id=str(next(ctx.uid)), from_user=u, message=holder, data=data, chat_instance=str(user_id)
        )
        await _DP.feed_update(bot, Update(update_id=next(ctx.uid), callback_query=cq), sessionmaker=sm)

    ctx.send = send
    ctx.tap = tap

    async def db_user(uid):
        async with sm() as s:
            return await s.get(User, uid)

    ctx.db_user = db_user
    yield ctx
    await engine.dispose()


async def seed_card(env, uid: int, rarity="common", name="Пивной животик", weight=10, price=600):
    async with env.sm() as s:
        card = UserCard(user_id=uid, rarity=rarity, name=name, weight=weight, defects=[], base_price=price)
        s.add(card)
        await s.commit()
        return card.id


async def seed_points(env, uid: int, points: int, fcoins: int = 0):
    async with env.sm() as s:
        u = await s.get(User, uid)
        u.points = points
        u.fcoins = fcoins
        await s.commit()


def last_call_of(env, cls):
    found = None
    for c in env.bot.calls:
        if isinstance(c, cls):
            found = c
    return found


@pytest.mark.asyncio
async def test_start_creates_user_and_referral(env):
    await env.send("/start", user_id=101, username="linuin")
    u = await env.db_user(101)
    assert u is not None and u.username == "linuin"
    assert any("Добро пожаловать" in t for t in env.bot.texts())

    await env.send("/start 101", user_id=202, username="friend")
    from sqlalchemy import select

    from fatbot.models import Referral

    async with env.sm() as s:
        ref = (await s.scalars(select(Referral).where(Referral.referrer_id == 101))).first()
    assert ref is not None and ref.referred_id == 202


@pytest.mark.asyncio
async def test_fcard_grants_card_then_cooldown(env):
    await env.send("/fcard", user_id=303, username="player")
    u = await env.db_user(303)
    assert u.cards_opened == 1
    assert u.next_card_at is not None
    joined = "\n".join(env.bot.texts())
    assert "Вам выпал жир!" in joined

    env.bot.calls.clear()
    await env.send("/fcard", user_id=303, username="player")
    joined = "\n".join(env.bot.texts())
    assert "еще раз через" in joined
    assert (await env.db_user(303)).cards_opened == 1


@pytest.mark.asyncio
async def test_pay_by_username(env):
    async with env.sm() as s:
        s.add(User(id=1, username="alice"))
        s.add(User(id=2, username="bob"))
        await s.commit()
    await seed_points(env, 1, 1000)

    await env.send("/pay @bob 400 привет", user_id=1, username="alice")
    a, b = await env.db_user(1), await env.db_user(2)
    assert a.points == 600 and b.points == 400


@pytest.mark.asyncio
async def test_pay_insufficient(env):
    async with env.sm() as s:
        s.add(User(id=1, username="alice"))
        s.add(User(id=2, username="bob"))
        await s.commit()
    await env.send("/pay @bob 999999", user_id=1, username="alice")
    assert any("Недостаточно" in t for t in env.bot.texts())
    assert (await env.db_user(2)).points == 0


@pytest.mark.asyncio
async def test_sellall_flow(env):
    async with env.sm() as s:
        s.add(User(id=9, username="seller"))
        await s.commit()
    for i in range(3):
        await seed_card(env, 9, "common", f"Жир{i}", 10, 500)
    await env.send("/sellall", user_id=9, username="seller")
    await env.tap("selr:common", user_id=9)
    await env.tap("selall_go:common", user_id=9)

    from sqlalchemy import func, select

    async with env.sm() as s:
        cnt = await s.scalar(
            select(func.count()).select_from(UserCard.__table__)
        )
    assert cnt == 0
    u = await env.db_user(9)
    assert u.points == 1500
    assert any("Продано 3 жиров" in t for t in env.bot.texts())


@pytest.mark.asyncio
async def test_upgrade_success(env):
    import random as _r

    real_random = _r.random
    _r.random = lambda: 0.0
    try:
        async with env.sm() as s:
            s.add(User(id=11, username="up"))
            await s.commit()
        cid = await seed_card(env, 11, "rare", "Отпускное пузо", 50, 30000)
        await seed_points(env, 11, 100000)
        await env.tap(f"upone:{cid}", user_id=11)
        await env.tap(f"upgo:{cid}", user_id=11)
    finally:
        _r.random = real_random

    from sqlalchemy import select

    async with env.sm() as s:
        cards = (await s.scalars(select(UserCard).where(UserCard.user_id == 11))).all()
    assert len(cards) == 1
    assert cards[0].rarity == "epic"
    assert any("Успех" in t for t in env.bot.texts())


@pytest.mark.asyncio
async def test_upgrade_failure_destroys_card(env):
    import random as _r

    real = _r.random
    _r.random = lambda: 0.99
    try:
        async with env.sm() as s:
            s.add(User(id=12, username="up2"))
            await s.commit()
        cid = await seed_card(env, 12, "common", "Диванный холмик", 8, 480)
        await seed_points(env, 12, 10000)
        await env.tap(f"upgo:{cid}", user_id=12)
    finally:
        _r.random = real

    from sqlalchemy import func, select

    async with env.sm() as s:
        cnt = await s.scalar(select(func.count()).select_from(UserCard.__table__))
    assert cnt == 0
    assert any("Неудача" in t for t in env.bot.texts())
    u = await env.db_user(12)
    assert u.points == 10000 - 5000


@pytest.mark.asyncio
async def test_avito_listing_and_buying(env):
    async with env.sm() as s:
        s.add(User(id=21, username="seller"))
        s.add(User(id=22, username="buyer"))
        await s.commit()
    await seed_card(env, 21, "epic", "Мраморное сало", 120, 720000)
    await seed_points(env, 22, 800000)

    await env.send("/avisell", user_id=21, username="seller")
    from sqlalchemy import select

    async with env.sm() as s:
        card = (await s.scalars(select(UserCard).where(UserCard.user_id == 21))).first()
    await env.tap(f"avpick:{card.id}", user_id=21, username="seller")
    await env.send("50000", user_id=21, username="seller")

    from fatbot.models import MarketListing

    async with env.sm() as s:
        listing = (await s.scalars(select(MarketListing).where(MarketListing.active == True))).first()  # noqa: E712
    assert listing is not None and listing.price == 50000

    await env.tap(f"avbuy:{listing.id}", user_id=22, username="buyer")
    async with env.sm() as s:
        card = await s.get(UserCard, listing.card_id)
        seller = await s.get(User, 21)
        buyer = await s.get(User, 22)
    assert card.user_id == 22
    assert buyer.points == 750000
    assert seller.points == int(50000 * 0.95)


@pytest.mark.asyncio
async def test_casino_coinflip(env):
    async with env.sm() as s:
        s.add(User(id=31, username="gambler"))
        await s.commit()
    await seed_points(env, 31, 10000)

    import random as _r

    real = _r.random
    _r.random = lambda: 0.0
    try:
        await env.tap("cf:1000", user_id=31)
    finally:
        _r.random = real

    u = await env.db_user(31)
    assert u.points == 11000
    assert u.casino_wins == 1


@pytest.mark.asyncio
async def test_daily_cycle(env):
    async with env.sm() as s:
        s.add(User(id=41, username="daily"))
        await s.commit()
    await env.tap("dly_go", user_id=41)
    u = await env.db_user(41)
    assert u.points == 10_000
    assert u.daily_day == 1

    await env.tap("dly_go", user_id=41)
    u2 = await env.db_user(41)
    assert u2.points == 10_000
    assert any("уже получали" in t for t in env.bot.texts())


@pytest.mark.asyncio
async def test_workshop_create_collect_upgrade(env):
    async with env.sm() as s:
        s.add(User(id=51, username="farmer"))
        await s.commit()
    await seed_points(env, 51, 3_000_000)

    await env.send("/newworkshop", user_id=51, username="farmer")
    await env.tap("wsnew_go", user_id=51)
    u = await env.db_user(51)
    assert u.workshop_lvl == 1
    assert u.points == 3_000_000 - 2_500_000

    async with env.sm() as s:
        from datetime import timedelta

        db_u = await s.get(User, 51)
        db_u.workshop_at = utcnow() - timedelta(hours=2)
        await s.commit()

    await env.tap("wscol", user_id=51)
    u = await env.db_user(51)
    assert u.points == 500_000 + 16_000

    await seed_points(env, 51, 1_500_000)
    before = (await env.db_user(51)).points
    await env.tap("wsupg", user_id=51)
    u = await env.db_user(51)
    assert u.workshop_lvl == 2
    assert u.points == before - 1_000_000


@pytest.mark.asyncio
async def test_trade_between_users(env):
    async with env.sm() as s:
        s.add(User(id=61, username="anna"))
        s.add(User(id=62, username="boris"))
        await s.commit()
    ca = await seed_card(env, 61, "common", "Жир Анны", 10, 600)
    cb_ = await seed_card(env, 62, "rare", "Жир Бориса", 40, 24000)

    await env.send("/trade @boris", user_id=61, username="anna")
    await env.tap(f"trf:{ca}", user_id=61, username="anna")
    await env.tap(f"tracc:61", user_id=62, username="boris")
    await env.tap(f"trt:{cb_}", user_id=62, username="boris")
    await env.tap("tryes", user_id=62, username="boris")

    from sqlalchemy import select

    async with env.sm() as s:
        a = await s.get(UserCard, ca)
        b = await s.get(UserCard, cb_)
    assert a.user_id == 62
    assert b.user_id == 61


@pytest.mark.asyncio
async def test_profile_view_counter(env):
    async with env.sm() as s:
        s.add(User(id=71, username="star"))
        s.add(User(id=72, username="viewer"))
        await s.commit()
    await env.send("/profile @star", user_id=72, username="viewer")
    from sqlalchemy import select

    from fatbot.models import Achievement, ProfileView

    async with env.sm() as s:
        views = (await s.scalars(select(ProfileView).where(ProfileView.target_id == 71))).all()
        ach = (await s.scalars(select(Achievement).where(Achievement.user_id == 71, Achievement.key == "star"))).all()
    assert len(views) == 1
    assert len(ach) == 1


@pytest.mark.asyncio
async def test_upgradeshop_purchase(env):
    async with env.sm() as s:
        s.add(User(id=81, username="shopper"))
        await s.commit()
    await seed_points(env, 81, 200000)
    await env.send("/upgradeshop", user_id=81, username="shopper")
    await env.tap("ubuy:luck", user_id=81)
    u = await env.db_user(81)
    assert u.luck_lvl == 1
    assert u.points == 200000 - 50_000


@pytest.mark.asyncio
async def test_fcard_text_command_ru(env):
    await env.send("ФКарточка", user_id=91, username="ru")
    u = await env.db_user(91)
    assert u.cards_opened == 1


@pytest.mark.asyncio
async def test_myfats_empty(env):
    await env.send("/myfats", user_id=95, username="empty")
    assert any("коллекция пуста" in t for t in env.bot.texts())


@pytest.mark.asyncio
async def test_fshop_buy_and_inventory(env):
    async with env.sm() as s:
        s.add(User(id=111, username="shopper2"))
        await s.commit()
    await env.send("/fshop", user_id=111, username="shopper2")
    await env.tap("accbuy:clip", user_id=111)
    assert any("Недостаточно F-Coins" in t for t in env.bot.texts())

    await seed_points(env, 111, 0, fcoins=10)
    await env.tap("accbuy:clip", user_id=111)
    u = await env.db_user(111)
    assert u.fcoins == 5

    await env.send("/finventory", user_id=111, username="shopper2")
    joined = "\n".join(env.bot.texts())
    assert "Зажим для похудения" in joined


@pytest.mark.asyncio
async def test_collection_browse_detail(env):
    async with env.sm() as s:
        s.add(User(id=121, username="collector"))
        await s.commit()
    cid = await seed_card(env, 121, "epic", "Мраморное сало", 120, 720000)
    await env.send("/myfats", user_id=121, username="collector")
    await env.tap("coll:epic", user_id=121)
    await env.tap(f"card:{cid}", user_id=121)
    joined = "\n".join(env.bot.texts())
    assert "Мраморное сало" in joined
    assert "Элитный" in joined


@pytest.mark.asyncio
async def test_avito_browse_empty_and_exchange(env):
    async with env.sm() as s:
        s.add(User(id=131, username="browser"))
        await s.commit()
    await env.send("/avito", user_id=131, username="browser")
    joined = "\n".join(env.bot.texts())
    assert "ЖироАвито" in joined

    await seed_points(env, 131, 500_000)
    await env.tap("accex", user_id=131)
    u = await env.db_user(131)
    assert u.fcoins == 0
    await seed_points(env, 131, 1_500_000)
    await env.tap("accex", user_id=131)
    u = await env.db_user(131)
    assert u.fcoins == 1
    assert u.points == 500_000
