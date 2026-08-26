import random
import re
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from . import data
from .models import Achievement, Accessory, BotSetting, MarketListing, ProfileView, Referral, User, UserCard
from .utils import utcnow


async def get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.get(BotSetting, key)
    return row.value if row else None


async def set_setting(session: AsyncSession, key: str, value: str):
    row = await session.get(BotSetting, key)
    if row is None:
        session.add(BotSetting(key=key, value=value))
    else:
        row.value = value
    await session.flush()


async def cooldown_disabled(session: AsyncSession) -> bool:
    return (await get_setting(session, "no_cooldown")) == "1"


async def get_or_create_user(session: AsyncSession, tg_id: int, username: str | None, full_name: str) -> User:
    user = await session.get(User, tg_id)
    if user is None:
        user = User(id=tg_id, username=username, full_name=full_name or "")
        session.add(user)
        await session.flush()
    else:
        user.username = username or user.username
        if full_name:
            user.full_name = full_name
        await session.flush()
    return user


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    q = select(User).where(func.lower(User.username) == username.lstrip("@").lower())
    return (await session.scalars(q)).first()


async def accessory_keys(session: AsyncSession, user_id: int) -> set[str]:
    q = select(Accessory.item_key).where(Accessory.user_id == user_id)
    return set((await session.scalars(q)).all())


async def has_accessory(session: AsyncSession, user_id: int, key: str) -> bool:
    q = select(Accessory).where(Accessory.user_id == user_id, Accessory.item_key == key)
    return (await session.scalars(q)).first() is not None


async def luck_bonus(session: AsyncSession, user: User) -> float:
    bonus = float(user.luck_lvl or 0)
    if await has_accessory(session, user.id, "fork"):
        bonus += 2.0
    return bonus


async def trader_bonus(session: AsyncSession, user: User) -> float:
    bonus = float(user.trader_lvl or 0)
    if await has_accessory(session, user.id, "scale"):
        bonus += 3.0
    return bonus


async def casino_edge(session: AsyncSession, user: User) -> float:
    if await has_accessory(session, user.id, "clover"):
        return 1.0
    return 0.0


async def effective_cooldown(session: AsyncSession, user: User) -> timedelta:
    base = max(600, 10800 - (user.speed_lvl or 0) * 180)
    keys = await accessory_keys(session, user.id)
    mult = max(0.70, 0.95 ** sum(1 for k in keys if k == "clip"))
    return timedelta(seconds=int(base * mult))


def roll_rarity(rng, luck_pct_value: float) -> str:
    weights = []
    for i, key in enumerate(data.ORDER):
        w = data.RARITIES[key]["chance"]
        if i > 0:
            w *= 1 + (luck_pct_value / 100.0) * i * 0.5
        weights.append(w)
    return rng.choices(data.ORDER, weights=weights)[0]


def make_card_fields(rarity: str, rng) -> dict:
    d = data.RARITIES[rarity]
    weight = rng.randint(d["min"], d["max"])
    defects = []
    flavor = rng.choice(data.FLAVORS_GOOD)
    if rng.random() < 0.35:
        defects = rng.sample(data.DEFECTS, rng.randint(1, 2))
        flavor = rng.choice(data.FLAVORS_BAD)
    name = rng.choice(data.NAMES[rarity])
    price = int(weight * d["ppk"] * (0.8 ** len(defects)))
    fields = {"rarity": rarity, "name": name, "weight": weight, "defects": defects, "base_price": price}
    return fields, flavor


async def roll_card(session: AsyncSession, user: User, rng=random) -> tuple[UserCard, str, str]:
    fields, flavor = make_card_fields(roll_rarity(rng, await luck_bonus(session, user)), rng)
    card = UserCard(user_id=user.id, **fields)
    session.add(card)
    user.cards_opened += 1
    await session.flush()
    ref_msg = await referral_card_milestone(session, user) or ""
    return card, flavor, ref_msg


async def referral_card_milestone(session: AsyncSession, user: User) -> str | None:
    q = select(Referral).where(Referral.referred_id == user.id, Referral.cards_bonus == False)  # noqa: E712
    ref = (await session.scalars(q)).first()
    if ref is None or user.cards_opened < 3:
        return None
    ref.cards_bonus = True
    for uid in (ref.referrer_id, ref.referred_id):
        u = await session.get(User, uid)
        if u:
            u.points += 50_000
    return "🎁 Вы и ваш пригласивший получили по 50,000 ФОчек за активность друга!"


def upgrade_chance(base_key: str, luck: float) -> float:
    return min(0.95, data.UPGRADE_CHANCE[base_key] + min(0.20, luck * 0.02))


async def do_upgrade(session: AsyncSession, user: User, card: UserCard, rng=random) -> tuple[bool, UserCard | None]:
    idx = data.ORDER.index(card.rarity)
    if idx + 1 >= len(data.ORDER):
        return False, None
    chance = upgrade_chance(card.rarity, await luck_bonus(session, user))
    success = rng.random() < chance
    await session.delete(card)
    await session.flush()
    if success:
        nk = data.ORDER[idx + 1]
        fields, _ = make_card_fields(nk, rng)
        new_card = UserCard(user_id=user.id, **fields)
        session.add(new_card)
        await session.flush()
        user.upgrades_done += 1
        return True, new_card
    return False, None


async def sell_cards(session: AsyncSession, user: User, cards: list[UserCard]) -> int:
    total = sum(c.base_price for c in cards)
    total = int(total * (1.0 + await trader_bonus(session, user) / 100.0))
    for c in cards:
        await session.delete(c)
    user.points += total
    user.sales_done += len(cards)
    await session.flush()
    return total


def status_name(total_weight: int) -> str:
    for threshold, name in data.STATUS_TIERS:
        if total_weight >= threshold:
            return name
    return "Обычный"


async def collection_stats(session: AsyncSession, user_id: int) -> dict:
    q = select(
        func.count(UserCard.id),
        func.coalesce(func.sum(UserCard.weight), 0),
        func.coalesce(func.sum(UserCard.base_price), 0),
    ).where(UserCard.user_id == user_id)
    count, weight, value = (await session.execute(q)).one()
    by_rarity = {}
    q2 = select(UserCard.rarity, func.count(UserCard.id)).where(UserCard.user_id == user_id).group_by(UserCard.rarity)
    for rarity, cnt in (await session.execute(q2)).all():
        by_rarity[rarity] = cnt
    return {"count": count, "weight": weight, "value": value, "by_rarity": by_rarity}


async def views_count(session: AsyncSession, user_id: int) -> int:
    q = select(func.count(ProfileView.id)).where(ProfileView.target_id == user_id)
    return (await session.scalar(q)) or 0


_AMOUNT_RE = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(кк|к|kk|k)?$", re.IGNORECASE)


def parse_amount(s: str) -> int | None:
    s = s.strip().replace(" ", "")
    m = _AMOUNT_RE.match(s)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    suf = (m.group(2) or "").lower()
    mult = {"к": 1_000, "k": 1_000, "кк": 1_000_000, "kk": 1_000_000}.get(suf, 1)
    result = int(val * mult)
    return result if result > 0 else None


async def transfer_points(session: AsyncSession, src: User, dst: User, amount: int):
    if amount <= 0:
        raise ValueError("Сумма должна быть больше нуля.")
    if src.id == dst.id:
        raise ValueError("Нельзя переводить самому себе.")
    if src.points < amount:
        raise ValueError("Недостаточно ФОчек.")
    src.points -= amount
    dst.points += amount
    await session.flush()


async def coinflip_win(rng, edge_pct: float = 0.0) -> bool:
    return rng.random() < min(0.60, 0.49 + edge_pct / 100.0)


def spin_slots(rng) -> tuple[tuple[str, str, str], float]:
    reels = tuple(rng.choices(data.SLOTS_SYMBOLS, k=3))
    if reels[0] == reels[1] == reels[2]:
        return reels, 12.0
    for s in set(reels):
        if reels.count(s) >= 2:
            return reels, 2.0
    return reels, 0.0


async def claim_daily(session: AsyncSession, user: User):
    now = utcnow()
    if user.daily_last is not None and now - user.daily_last < timedelta(hours=24):
        return None
    if user.daily_last is not None and now - user.daily_last > timedelta(hours=48):
        user.daily_day = 0
    user.daily_day += 1
    day = user.daily_day
    reward = data.DAILY_REWARDS[min(day, 7) - 1]
    fc = 1 if day == 7 else 0
    user.points += reward
    user.fcoins += fc
    user.daily_last = now
    completed_cycle = day == 7
    if completed_cycle:
        user.daily_day = 0
    await session.flush()
    ref_msg = ""
    if completed_cycle:
        q = select(Referral).where(Referral.referred_id == user.id, Referral.daily_bonus == False)  # noqa: E712
        ref = (await session.scalars(q)).first()
        if ref is not None:
            ref.daily_bonus = True
            for uid in (ref.referrer_id, ref.referred_id):
                u = await session.get(User, uid)
                if u:
                    u.points += 100_000
            ref_msg = "🎁 Вы и ваш пригласивший получили по 100,000 ФОчек за завершение 7-дневного цикла!"
    return day, reward, fc, completed_cycle, ref_msg


def workshop_income_hour(user: User) -> int:
    return int(data.WORKSHOP_BASE_HOUR * (user.workshop_lvl or 0) * (1 + 0.05 * (user.farmer_lvl or 0)))


def workshop_pending(user: User, now=None) -> int:
    if user.workshop_lvl == 0 or user.workshop_at is None:
        return 0
    now = now or utcnow()
    hours = min((now - user.workshop_at).total_seconds() / 3600.0, 24)
    return int(hours * workshop_income_hour(user))


def workshop_collect(user: User) -> int:
    amount = workshop_pending(user)
    if amount > 0:
        user.points = (user.points or 0) + amount
        user.workshop_at = utcnow()
    return amount


async def buy_accessory(session: AsyncSession, user: User, key: str) -> Accessory | None:
    item = data.ACCESSORY_BY_KEY.get(key)
    if item is None or await has_accessory(session, user.id, key):
        return None
    if user.fcoins < item["price"]:
        return None
    user.fcoins -= item["price"]
    acc = Accessory(user_id=user.id, item_key=key)
    session.add(acc)
    await session.flush()
    return acc


async def exchange_fcoin(session: AsyncSession, user: User) -> bool:
    if user.points < 1_000_000:
        return False
    user.points -= 1_000_000
    user.fcoins += 1
    await session.flush()
    return True


async def buy_upgrade_level(session: AsyncSession, user: User, key: str) -> bool:
    lvl = getattr(user, f"{key}_lvl")
    if lvl >= data.UPGRADE_MAX_LVL:
        return False
    cost = data.UPGRADE_COST(lvl)
    if user.points < cost:
        return False
    user.points -= cost
    setattr(user, f"{key}_lvl", lvl + 1)
    await session.flush()
    return True


async def grant_achievements(session: AsyncSession, user: User) -> list[str]:
    stats = await collection_stats(session, user.id)
    views = await views_count(session, user.id)
    conditions = {
        "first_card": stats["count"] >= 1,
        "ten_cards": stats["count"] >= 10,
        "centner": stats["weight"] >= 100,
        "millionaire": stats["value"] >= 1_000_000,
        "upgrader": user.upgrades_done >= 1,
        "seller": user.sales_done >= 1,
        "gambler": user.casino_wins >= 1,
        "star": views >= 1,
    }
    owned = set((await session.scalars(select(Achievement.key).where(Achievement.user_id == user.id))).all())
    titles = dict(data.ACHIEVEMENTS)
    granted = []
    for key, earned in conditions.items():
        if earned and key not in owned:
            session.add(Achievement(user_id=user.id, key=key))
            granted.append(titles[key])
    await session.flush()
    return granted


async def register_referral(session: AsyncSession, new_user: User, payload: int) -> bool:
    if payload == new_user.id:
        return False
    q = select(Referral).where(Referral.referred_id == new_user.id)
    if (await session.scalars(q)).first() is not None:
        return False
    if await session.get(User, payload) is None:
        return False
    session.add(Referral(referrer_id=payload, referred_id=new_user.id))
    await session.flush()
    return True
