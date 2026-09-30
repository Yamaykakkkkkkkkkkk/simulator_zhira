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


async def get_user_setting(session: AsyncSession, user_id: int, key: str) -> str | None:
    from .models import UserSetting
    row = await session.get(UserSetting, (user_id, key))
    return row.value if row else None


async def set_user_setting(session: AsyncSession, user_id: int, key: str, value: str):
    from .models import UserSetting
    row = await session.get(UserSetting, (user_id, key))
    if row is None:
        session.add(UserSetting(user_id=user_id, key=key, value=value))
    else:
        row.value = value
    await session.flush()


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
    if await has_accessory(session, user.id, "trophy"):
        bonus += 2.0
    return bonus


async def trader_bonus(session: AsyncSession, user: User) -> float:
    bonus = float(user.trader_lvl or 0)
    if await has_accessory(session, user.id, "scale"):
        bonus += 3.0
    return bonus


async def casino_edge(session: AsyncSession, user: User) -> float:
    edge = 0.0
    if await has_accessory(session, user.id, "clover"):
        edge += 1.0
    if await has_accessory(session, user.id, "horseshoe"):
        edge += 1.0
    edge += 0.5 * float(getattr(user, "gambler_lvl", 0) or 0)
    return edge


async def effective_cooldown(session: AsyncSession, user: User) -> timedelta:
    base = max(600, 10800 - (user.speed_lvl or 0) * 180)
    keys = await accessory_keys(session, user.id)
    n = sum(1 for k in keys if k == "clip")
    # песочные часы стакаются с зажимом
    n += sum(1 for k in keys if k == "hourglass")
    mult = max(0.70, 0.95 ** n)
    return timedelta(seconds=int(base * mult))


def roll_rarity(rng, luck_pct_value: float) -> str:
    weights = []
    for i, key in enumerate(data.ORDER):
        w = data.RARITIES[key]["chance"]
        if i > 0:
            w *= 1 + (luck_pct_value / 100.0) * i * 0.5
        weights.append(w)
    return rng.choices(data.ORDER, weights=weights)[0]


# блестящие варианты кодируются суффиксом в name, без новых колонок БД
def strip_variant_suffix(name: str) -> str:
    for suffix in (f" {data.GOLDEN_SUFFIX}", f" {data.SHINY_SUFFIX}"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def card_variant(name: str) -> str | None:
    if name.endswith(f" {data.GOLDEN_SUFFIX}"):
        return "golden"
    if name.endswith(f" {data.SHINY_SUFFIX}"):
        return "shiny"
    return None


def make_card_fields(rarity: str, rng, shiny_bonus: float = 0.0) -> dict:
    d = data.RARITIES[rarity]
    weight = rng.randint(d["min"], d["max"])
    defects = []
    flavor = rng.choice(data.FLAVORS_GOOD)
    if rng.random() < 0.35:
        defects = rng.sample(data.DEFECTS, rng.randint(1, 2))
        flavor = rng.choice(data.FLAVORS_BAD)
    name = rng.choice(data.NAMES[rarity])
    price_mult = 1.0
    roll = rng.random()
    if roll < data.GOLDEN_CHANCE:
        name = f"{name} {data.GOLDEN_SUFFIX}"
        price_mult = data.GOLDEN_PRICE_MULT
    # коллекционер и магнит повышают шанс shiny (аддитивно)
    elif roll < data.GOLDEN_CHANCE + data.SHINY_CHANCE + max(0.0, shiny_bonus):
        name = f"{name} {data.SHINY_SUFFIX}"
        weight = int(weight * data.SHINY_WEIGHT_MULT)
        price_mult = data.SHINY_PRICE_MULT
    price = int(weight * d["ppk"] * (0.8 ** len(defects)) * price_mult)
    fields = {"rarity": rarity, "name": name, "weight": weight, "defects": defects, "base_price": price}
    return fields, flavor


def collection_set_bonus(owned_names) -> dict:
    owned_base = {strip_variant_suffix(n) for n in owned_names}
    completed = []
    progress = []
    total = 0
    for s in data.COLLECTION_SETS:
        need = list(s["names"])
        have = [n for n in need if n in owned_base]
        missing = [n for n in need if n not in owned_base]
        if not missing:
            completed.append(s)
            total += s["bonus"]
        progress.append({"key": s["key"], "name": s["name"], "have": len(have),
                         "need": len(need), "missing": missing, "bonus": s["bonus"],
                         "completed": not missing})
    return {"total_bonus": total, "completed": completed, "progress": progress}


async def user_collection_set_bonus(session: AsyncSession, user_id: int) -> dict:
    q = select(UserCard.name).where(UserCard.user_id == user_id)
    names = list((await session.scalars(q)).all())
    return collection_set_bonus(names)


async def roll_card(session: AsyncSession, user: User, rng=random) -> tuple[UserCard, str, str]:
    fields, flavor = make_card_fields(
        roll_rarity(rng, await luck_bonus(session, user)), rng, await shiny_chance(session, user)
    )
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
    if success:
        await session.delete(card)
        await session.flush()
        nk = data.ORDER[idx + 1]
        fields, _ = make_card_fields(nk, rng)
        new_card = UserCard(user_id=user.id, **fields)
        session.add(new_card)
        await session.flush()
        user.upgrades_done += 1
        return True, new_card
    # хранитель может спасти жир от сгорания (карта выживает)
    if rng.random() * 100.0 < await upgrade_protection(session, user):
        await session.flush()
        return False, card
    await session.delete(card)
    await session.flush()
    return False, None


async def sell_cards(session: AsyncSession, user: User, cards: list[UserCard]) -> int:
    total = sum(c.base_price for c in cards)
    total = int(total * (1.0 + await trader_bonus(session, user) / 100.0))
    total = int(total * prestige_bonus(user))
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
    lvl = user.workshop_lvl or 0
    if lvl <= 5:
        base = data.WORKSHOP_BASE_HOUR * lvl
    else:
        base = int(data.WORKSHOP_BASE_HOUR * (lvl * 2 - 5))
    return int(base * (1 + 0.05 * (user.farmer_lvl or 0)) * prestige_bonus(user))


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
    if key not in set(data.UPGRADE_KEYS):
        return False
    try:
        lvl = getattr(user, f"{key}_lvl")
    except AttributeError:
        return False
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
    from .models import Container, Farm, UserQuest

    by_r = stats.get("by_rarity", {})
    # квесты завершённые
    q_completed = await session.scalar(
        select(func.count()).select_from(UserQuest).where(
            UserQuest.user_id == user.id, UserQuest.completed == True  # noqa: E712
        )
    ) or 0
    # ферма / контейнеры
    has_farm = (await session.scalars(select(Farm).where(Farm.user_id == user.id))).first() is not None
    has_container = (await session.scalar(select(func.count()).select_from(Container).where(Container.user_id == user.id)) or 0) > 0
    story_step = getattr(user, "story_step", 0) or 0
    story_half = len(data.STORY_QUESTS) // 2 if hasattr(data, "STORY_QUESTS") else 9
    story_total = len(data.STORY_QUESTS) if hasattr(data, "STORY_QUESTS") else 18
    conditions = {
        "first_card": stats["count"] >= 1,
        "ten_cards": stats["count"] >= 10,
        "centner": stats["weight"] >= 100,
        "millionaire": stats["value"] >= 1_000_000,
        "upgrader": (user.upgrades_done or 0) >= 1,
        "seller": (user.sales_done or 0) >= 1,
        "gambler": (user.casino_wins or 0) >= 1,
        "star": views >= 1,
        "fifty_cards": stats["count"] >= 50,
        "hundred_cards": (user.cards_opened or 0) >= 100 or stats["count"] >= 100,
        "ton_weight": stats["weight"] >= 1000,
        "ten_millionaire": stats["value"] >= 10_000_000,
        "rich": (user.points or 0) >= 1_000_000,
        "upgrader5": (user.upgrades_done or 0) >= 5,
        "seller10": (user.sales_done or 0) >= 10,
        "gambler10": (user.casino_wins or 0) >= 10,
        "mythic_owner": by_r.get("mythic", 0) >= 1,
        "legendary_hunter": by_r.get("legendary", 0) >= 1 or by_r.get("mythic", 0) >= 1,
        "workshop_owner": (user.workshop_lvl or 0) >= 1,
        "workshop_magnate": (user.workshop_lvl or 0) >= 5,
        "farmer": has_farm,
        "keeper": has_container,
        "quest_master": q_completed >= 5,
        "story_half": story_step >= story_half,
        "story_done": story_step >= story_total,
    }
    owned = set((await session.scalars(select(Achievement.key).where(Achievement.user_id == user.id))).all())
    titles = dict(data.ACHIEVEMENTS)
    granted = []
    for key, earned in conditions.items():
        if earned and key not in owned and key in titles:
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


def _quest_reset_at(quest_type: str, now) -> object:
    """Граница сброса: daily — полночь, weekly — понедельник 00:00, story — не сбрасывается."""
    from datetime import timedelta

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if quest_type == "weekly":
        days_ahead = 7 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return midnight + timedelta(days=days_ahead)
    if quest_type == "story":
        return midnight + timedelta(days=365 * 10)
    return midnight + timedelta(days=1)


def _reset_expired_quest(quest, now=None) -> bool:
    """Сбросить квест, если срок вышел. Возвращает True, если был сброшен.

    Раньше reset_at записывался, но нигде не читался — поэтому выполненный ежедневный
    квест навсегда оставался completed=True и больше никогда не давал награду.
    """
    if quest is None or getattr(quest, "quest_type", "daily") == "story":
        return False
    now = now or utcnow()
    reset_at = getattr(quest, "reset_at", None)
    if reset_at is None or now < reset_at:
        return False
    quest.progress = 0
    quest.completed = False
    quest.claimed = False
    quest.reset_at = _quest_reset_at(quest.quest_type or "daily", now)
    return True


async def get_quest_progress(session: AsyncSession, user_id: int, quest_key: str):
    from .models import UserQuest
    q = select(UserQuest).where(UserQuest.user_id == user_id, UserQuest.quest_key == quest_key)
    quest = (await session.scalars(q)).first()
    if _reset_expired_quest(quest):
        await session.flush()
    return quest


async def purge_stale_quests(session: AsyncSession, keep_days: int = 7) -> int:
    """Удалить строки квестов, протухших сильнее keep_days (таблица иначе растёт вечно)."""
    from .models import UserQuest

    cutoff = utcnow() - timedelta(days=keep_days)
    q = select(UserQuest).where(UserQuest.reset_at < cutoff)
    rows = list((await session.scalars(q)).all())
    for row in rows:
        await session.delete(row)
    if rows:
        await session.flush()
    return len(rows)


async def get_user_quests_with_progress(session: AsyncSession, user_id: int) -> dict[str, int]:
    """Квесты игрока с ненулевым прогрессом: {quest_key: progress}.

    Нужно, чтобы прогресс не пропадал из виду: хендлеры засчитывают фиксированные
    ключи (open5, sell3, ...), а ротация показывает игроку только 3 случайных квеста.
    """
    from .models import UserQuest

    q = select(UserQuest).where(UserQuest.user_id == user_id)
    rows = list((await session.scalars(q)).all())
    now = utcnow()
    out: dict[str, int] = {}
    for row in rows:
        if _reset_expired_quest(row, now):
            continue
        if (row.progress or 0) > 0 and not row.claimed:
            out[row.quest_key] = row.progress
    if rows:
        await session.flush()
    return out


async def update_quest_progress(session: AsyncSession, user_id: int, quest_key: str, amount: int = 1):
    from .models import UserQuest
    from .data import DAILY_QUESTS, WEEKLY_QUESTS

    story_defs = getattr(data, "STORY_QUESTS", [])
    quest_def = None
    for q in DAILY_QUESTS + WEEKLY_QUESTS + story_defs:
        if q["key"] == quest_key:
            quest_def = q
            break
    if not quest_def:
        return

    weekly_keys = {q["key"] for q in WEEKLY_QUESTS}
    story_keys = {q["key"] for q in story_defs}
    if quest_key in story_keys:
        qtype = "story"
    elif quest_key in weekly_keys:
        qtype = "weekly"
    else:
        qtype = "daily"

    now = utcnow()
    q = select(UserQuest).where(UserQuest.user_id == user_id, UserQuest.quest_key == quest_key)
    quest = (await session.scalars(q)).first()

    if quest is None:
        quest = UserQuest(
            user_id=user_id,
            quest_key=quest_key,
            quest_type=qtype,
            progress=0,
            target=quest_def["target"],
            reward=quest_def["reward"],
            reward_fcoins=int(quest_def.get("reward_fcoins", 0) or 0),
            completed=False,
            claimed=False,
            reset_at=_quest_reset_at(qtype, now),
        )
        session.add(quest)
    else:
        # синхронизируем target/reward с data.py для обратной совместимости
        quest.target = quest_def["target"]
        quest.reward = quest_def["reward"]
        quest.reward_fcoins = int(quest_def.get("reward_fcoins", 0) or 0)
        # новый цикл: старый прогресс больше не засчитывается
        _reset_expired_quest(quest, now)

    if not quest.completed:
        quest.progress = min((quest.progress or 0) + amount, quest.target)
        if quest.progress >= quest.target:
            quest.completed = True
    await session.flush()


async def claim_quest(session: AsyncSession, user_id: int, quest_key: str):
    from .models import UserQuest

    quest = await get_quest_progress(session, user_id, quest_key)
    if quest is None or not quest.completed or quest.claimed:
        return None

    quest.claimed = True
    user = await session.get(User, user_id)
    if user:
        user.points = (user.points or 0) + (quest.reward or 0)
        user.fcoins = (user.fcoins or 0) + (quest.reward_fcoins or 0)
    await session.flush()
    return quest.reward


# ротация 3 daily из 12 и 3 weekly из 10 (детерминировано по игроку и дате)
def _daily_seed(user_id: int, now=None) -> int:
    from .utils import utcnow as _u
    now = now or _u()
    day_num = now.replace(hour=0, minute=0, second=0, microsecond=0).toordinal()
    return int(user_id) * 100000 + day_num


def _weekly_seed(user_id: int, now=None) -> int:
    from .utils import utcnow as _u
    now = now or _u()
    monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    return int(user_id) * 100000 + monday.toordinal()


def get_user_daily_quests(user_id: int, now=None) -> list[dict]:
    import random as _r
    defs = list(data.DAILY_QUESTS)
    if len(defs) <= 3:
        return defs
    rng = _r.Random(_daily_seed(user_id, now))
    return rng.sample(defs, 3)


def get_user_weekly_quests(user_id: int, now=None) -> list[dict]:
    import random as _r
    defs = list(data.WEEKLY_QUESTS)
    if len(defs) <= 3:
        return defs
    rng = _r.Random(_weekly_seed(user_id, now))
    return rng.sample(defs, 3)


async def claim_all_quests(session: AsyncSession, user_id: int, quest_keys: list[str] | None = None):
    from .models import UserQuest
    total_points = 0
    total_fcoins = 0
    claimed_keys: list[str] = []
    if quest_keys is None:
        # по умолчанию: активные ротационные + все story
        act = [q["key"] for q in get_user_daily_quests(user_id)] + [q["key"] for q in get_user_weekly_quests(user_id)]
        story_keys = [q["key"] for q in getattr(data, "STORY_QUESTS", [])]
        quest_keys = act + story_keys
    for key in quest_keys:
        quest = await get_quest_progress(session, user_id, key)
        if quest is None or not quest.completed or quest.claimed:
            continue
        quest.claimed = True
        total_points += quest.reward or 0
        total_fcoins += quest.reward_fcoins or 0
        claimed_keys.append(key)
    if (total_points or total_fcoins) and (user := await session.get(User, user_id)):
        user.points = (user.points or 0) + total_points
        user.fcoins = (user.fcoins or 0) + total_fcoins
    await session.flush()
    return claimed_keys, total_points, total_fcoins


async def story_progress(session: AsyncSession, user: User):
    defs = list(getattr(data, "STORY_QUESTS", []))
    if not defs:
        return None, None, None
    idx = int(getattr(user, "story_step", 0) or 0)
    if idx >= len(defs):
        return len(defs), None, None
    qdef = defs[idx]
    qrow = await get_quest_progress(session, user.id, qdef["key"])
    return idx, qdef, qrow


async def claim_story(session: AsyncSession, user_id: int):
    user = await session.get(User, user_id)
    if user is None:
        return None
    defs = list(getattr(data, "STORY_QUESTS", []))
    idx = int(getattr(user, "story_step", 0) or 0)
    if idx >= len(defs):
        return None
    qdef = defs[idx]
    quest = await get_quest_progress(session, user_id, qdef["key"])
    if quest is None or not quest.completed or quest.claimed:
        return None
    quest.claimed = True
    user.points = (user.points or 0) + int(qdef.get("reward", 0))
    user.fcoins = (user.fcoins or 0) + int(qdef.get("reward_fcoins", 0) or 0)
    user.story_step = idx + 1
    await session.flush()
    # ачивки за половину/финал
    try:
        await grant_achievements(session, user)
    except Exception:
        pass
    return qdef


def calc_xp(user: User) -> int:
    return (
        int(user.cards_opened or 0) * 10
        + int(user.upgrades_done or 0) * 50
        + int(user.sales_done or 0) * 20
        + int(user.casino_wins or 0) * 30
    )


def player_level(user: User) -> dict:
    xp = calc_xp(user)
    levels = list(getattr(data, "PLAYER_LEVELS", []))
    if not levels:
        return {"lvl": 1, "title": "Новичок", "xp": xp, "xp_next": 100, "xp_cur": 0}
    cur = levels[0]
    nxt = None
    for i, lv in enumerate(levels):
        if xp >= lv["xp"]:
            cur = lv
            nxt = levels[i + 1] if i + 1 < len(levels) else None
        else:
            nxt = lv
            break
    return {
        "lvl": cur["lvl"],
        "title": cur["title"],
        "xp": xp,
        "xp_cur": cur["xp"],
        "xp_next": nxt["xp"] if nxt else cur["xp"],
        "next_lvl": nxt["lvl"] if nxt else cur["lvl"],
    }


def is_season_active(now=None) -> bool:
    from datetime import datetime
    from .utils import utcnow as _u
    now = now or _u()
    try:
        ev = getattr(data, "SEASON_EVENT", None)
        if not ev:
            return False
        start = datetime.fromisoformat(ev["start"])
        end = datetime.fromisoformat(ev["end"])
        return start <= now.replace(tzinfo=None) <= end
    except Exception:
        return False


async def claim_season_bonus(session: AsyncSession, user: User):
    from .models import UserSetting
    if not is_season_active():
        return None, "Сезон сейчас неактивен."
    ev = data.SEASON_EVENT
    season_key = f"season_claimed:{ev['start']}_{ev['end']}"
    row = await session.get(UserSetting, (user.id, season_key))
    if row is not None:
        return None, "Бонус сезона уже забран."
    mult = int(ev.get("multiplier", 2) or 2)
    bonus = int(ev.get("bonus", 50_000) or 50_000)
    amount = bonus * mult // 2 if mult == 2 else bonus
    # x2 к daily: выдаём удвоенный бонус первого дня
    base = data.DAILY_REWARDS[0] if data.DAILY_REWARDS else 10_000
    amount = max(amount, base * mult)
    user.points = (user.points or 0) + amount
    session.add(UserSetting(user_id=user.id, key=season_key, value="1"))
    await session.flush()
    return amount, None


async def get_containers(session: AsyncSession, user_id: int):
    from .models import Container
    q = select(Container).where(Container.user_id == user_id)
    return list((await session.scalars(q)).all())


async def total_container_capacity(session: AsyncSession, user_id: int) -> int:
    containers = await get_containers(session, user_id)
    return sum(c.capacity for c in containers)


async def buy_container(session: AsyncSession, user_id: int, ctype: str):
    from .models import Container
    from .data import CONTAINER_BY_KEY, MAX_CONTAINERS

    item = CONTAINER_BY_KEY.get(ctype)
    if item is None:
        return None, "Тип контейнера не найден."

    containers = await get_containers(session, user_id)
    if len(containers) >= MAX_CONTAINERS:
        return None, "У вас максимальное количество контейнеров."

    user = await session.get(User, user_id)
    if user.points < item["price"]:
        return None, "Недостаточно ФОчек."

    user.points -= item["price"]
    container = Container(user_id=user_id, ctype=ctype, capacity=item["capacity"])
    session.add(container)
    await session.flush()
    return container, None


async def buy_fatshop_card(session: AsyncSession, user: User, rarity: str, card_name: str):
    from .data import RARITIES, FATSHOP_PRICES
    import random as _r

    d = RARITIES.get(rarity)
    if d is None:
        return None, "Редкость не найдена."

    price = FATSHOP_PRICES.get(rarity, 1000)
    if user.points < price:
        return None, "Недостаточно ФОчек."

    weight = _r.randint(d["min"], d["max"])
    defects = []
    if _r.random() < 0.2:
        from .data import DEFECTS
        defects = _r.sample(DEFECTS, _r.randint(1, 2))

    card_price = int(weight * d["ppk"] * (0.8 ** len(defects)))
    card = UserCard(
        user_id=user.id,
        rarity=rarity,
        name=card_name,
        weight=weight,
        defects=defects,
        base_price=card_price,
    )
    session.add(card)
    user.points -= price
    user.cards_opened += 1
    await session.flush()
    return card, None


async def get_achievements_catalog(session: AsyncSession, user_id: int):
    from .models import Achievement
    from .data import ACHIEVEMENTS

    owned = set(
        (await session.scalars(select(Achievement.key).where(Achievement.user_id == user_id))).all()
    )

    catalog = []
    for key, title in ACHIEVEMENTS:
        catalog.append({
            "key": key,
            "title": title,
            "owned": key in owned,
        })
    return catalog


async def get_workshops(session: AsyncSession, limit: int = 10):
    q = select(User).where(User.workshop_lvl > 0).order_by(User.workshop_lvl.desc()).limit(limit)
    return list((await session.scalars(q)).all())


async def create_auction(session: AsyncSession, seller_id: int, card_id: int, starting_bid: int):
    from .models import Auction
    from datetime import timedelta
    from .utils import utcnow

    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != seller_id or card.listed:
        return None, "Жир недоступен."

    existing = await session.scalars(
        select(Auction).where(Auction.card_id == card_id, Auction.ends_at > utcnow())
    )
    if existing.first() is not None:
        return None, "Жир уже на аукционе."

    auction = Auction(
        seller_id=seller_id,
        card_id=card_id,
        current_bid=starting_bid,
        ends_at=utcnow() + timedelta(hours=24),
    )
    session.add(auction)
    card.listed = True
    await session.flush()
    return auction, None


async def place_bid(session: AsyncSession, auction_id: int, bidder_id: int, amount: int):
    from .models import Auction
    from .utils import utcnow

    auction = await session.get(Auction, auction_id)
    if auction is None or auction.ends_at <= utcnow():
        return None, "Аукцион не найден или завершён."

    if auction.seller_id == bidder_id:
        return None, "Нельзя ставить на свой лот."

    if amount <= auction.current_bid:
        return None, "Ставка должна быть больше текущей."

    bidder = await session.get(User, bidder_id)
    if bidder.points < amount:
        return None, "Недостаточно ФОчек."

    if auction.current_bidder is not None:
        prev_bidder = await session.get(User, auction.current_bidder)
        if prev_bidder:
            prev_bidder.points += auction.current_bid

    bidder.points -= amount
    auction.current_bid = amount
    auction.current_bidder = bidder_id
    await session.flush()
    return auction, None


async def get_farm(session: AsyncSession, user_id: int):
    from .models import Farm
    q = select(Farm).where(Farm.user_id == user_id)
    return (await session.scalars(q)).first()


async def create_farm(session: AsyncSession, user_id: int, cost: int):
    from .models import Farm

    user = await session.get(User, user_id)
    if user.points < cost:
        return None, "Недостаточно ФОчек."

    user.points -= cost
    farm = Farm(user_id=user_id)
    session.add(farm)
    await session.flush()
    return farm, None


def farm_calories_per_hour(farm) -> int:
    from .data import FARM_PRODUCTS_BY_KEY, FARM_LEVELS

    level_data = next((l for l in FARM_LEVELS if l["lvl"] == farm.level), FARM_LEVELS[0])
    efficiency = level_data["efficiency"]

    total = 0
    for i in range(1, level_data["slots"] + 1):
        product_key = getattr(farm, f"slot{i}_product", None)
        if product_key and product_key in FARM_PRODUCTS_BY_KEY:
            total += FARM_PRODUCTS_BY_KEY[product_key]["calories"]

    return int(total * efficiency)


def farm_slots_used(farm) -> int:
    from .data import FARM_LEVELS

    level_data = next((l for l in FARM_LEVELS if l["lvl"] == farm.level), FARM_LEVELS[0])
    used = 0
    for i in range(1, level_data["slots"] + 1):
        if getattr(farm, f"slot{i}_product", None):
            used += 1
    return used


def farm_max_slots(farm) -> int:
    from .data import FARM_LEVELS

    level_data = next((l for l in FARM_LEVELS if l["lvl"] == farm.level), FARM_LEVELS[0])
    return level_data["slots"]


def farm_pending_points(farm, bonus: float = 1.0) -> int:
    from .data import FARM_CALORIE_TO_POINTS

    if not farm.is_running or farm.total_calories <= 0:
        return 0
    # бонус кухни применяется при конвертации
    return int(farm.total_calories * FARM_CALORIE_TO_POINTS * bonus)


async def farm_collect(session: AsyncSession, farm, bonus: float | None = None) -> int:
    from .data import FARM_CALORIE_TO_POINTS
    from .utils import utcnow

    if bonus is None:
        # по умолчанию считаем полный бонус кухни владельца
        user = await session.get(User, farm.user_id)
        bonus = await farm_bonus(session, user) if user is not None else 1.0
    amount = farm_pending_points(farm, bonus)
    if amount > 0:
        user = await session.get(User, farm.user_id)
        if user:
            user.points += amount
        farm.total_calories = 0
        farm.last_collect = utcnow()
    await session.flush()
    return amount


async def place_food_in_slot(session: AsyncSession, farm, slot: int, product_key: str):
    from .data import FARM_PRODUCTS_BY_KEY, FARM_LEVELS

    product = FARM_PRODUCTS_BY_KEY.get(product_key)
    if product is None:
        return False, "Блюдо не найдено."

    level_data = next((l for l in FARM_LEVELS if l["lvl"] == farm.level), FARM_LEVELS[0])
    if slot < 1 or slot > level_data["slots"]:
        return False, f"Слот {slot} недоступен (макс. {level_data['slots']})."

    current = getattr(farm, f"slot{slot}_product", None)
    if current:
        return False, "Слот уже занят. Сначала уберите текущее блюдо."

    user = await session.get(User, farm.user_id)
    if user.points < product["price"]:
        return False, "Недостаточно ФОчек."

    user.points -= product["price"]
    setattr(farm, f"slot{slot}_product", product_key)
    await session.flush()
    return True, None


async def remove_food_from_slot(session: AsyncSession, farm, slot: int):
    from .data import FARM_LEVELS

    level_data = next((l for l in FARM_LEVELS if l["lvl"] == farm.level), FARM_LEVELS[0])
    if slot < 1 or slot > level_data["slots"]:
        return False, "Неверный слот."

    current = getattr(farm, f"slot{slot}_product", None)
    if not current:
        return False, "Слот уже пустой."

    setattr(farm, f"slot{slot}_product", None)
    await session.flush()
    return True, None


async def upgrade_farm(session: AsyncSession, farm):
    from .data import FARM_LEVELS

    if farm.level >= len(FARM_LEVELS):
        return False, "Максимальный уровень."

    next_level = next((l for l in FARM_LEVELS if l["lvl"] == farm.level + 1), None)
    if next_level is None:
        return False, "Максимальный уровень."

    user = await session.get(User, farm.user_id)
    if user.points < next_level["upgrade_cost"]:
        return False, "Недостаточно ФОчек."

    user.points -= next_level["upgrade_cost"]
    farm.level = next_level["lvl"]
    await session.flush()
    return True, None


def prestige_bonus(user: User) -> float:
    """Множитель дохода за престиж: +10% навсегда за каждый уровень."""
    return 1.0 + float(data.PRESTIGE_INCOME_PER_LVL) * float(getattr(user, "prestige_lvl", 0) or 0)


async def shiny_chance(session: AsyncSession, user: User) -> float:
    """Шанс shiny-жира (доля, напр. 0.01 = +1%): коллекционер + магнит."""
    chance = 0.01 * float(getattr(user, "collector_lvl", 0) or 0)
    if await has_accessory(session, user.id, "magnet"):
        chance += 0.02
    return chance


async def market_fee(session: AsyncSession, user: User) -> float:
    """Комиссия Авито с учётом аукциониста и сейфа (не ниже 0)."""
    fee = float(data.MARKET_FEE) - 0.01 * float(getattr(user, "auctioneer_lvl", 0) or 0)
    if await has_accessory(session, user.id, "vault"):
        fee -= 0.01
    return max(0.0, fee)


async def farm_bonus(session: AsyncSession, user: User) -> float:
    """Множитель дохода фермы: повар + фартук/колпак + престиж."""
    mult = 1.0 + 0.03 * float(getattr(user, "chef_lvl", 0) or 0)
    keys = await accessory_keys(session, user.id)
    if "apron" in keys:
        mult *= 1.05
    if "chef_hat" in keys:
        mult *= 1.10
    return mult * prestige_bonus(user)


async def upgrade_protection(session: AsyncSession, user: User) -> float:
    """Шанс (%) спасти жир при неудачном апгрейде: хранитель + амулет."""
    prot = 1.0 * float(getattr(user, "keeper_lvl", 0) or 0)
    if await has_accessory(session, user.id, "amulet"):
        prot += 3.0
    return prot


def prestige_available(user: User) -> tuple[bool, str]:
    """Проверка требований престижа: 100M ФОчек + 100 открытых жиров."""
    if (user.points or 0) < data.PRESTIGE_POINTS_REQ:
        return False, f"Нужно {data.PRESTIGE_POINTS_REQ:,} ФОчек (не хватает {data.PRESTIGE_POINTS_REQ - (user.points or 0):,})."
    if (user.cards_opened or 0) < data.PRESTIGE_CARDS_REQ:
        return False, f"Нужно открыть {data.PRESTIGE_CARDS_REQ} жиров (открыто {user.cards_opened or 0})."
    return True, ""


async def do_prestige(session: AsyncSession, user: User) -> tuple[bool, str]:
    """Престиж: сброс points/cards_opened/веток, +10% к доходу навсегда за уровень."""
    ok, reason = prestige_available(user)
    if not ok:
        return False, reason
    user.points = 0
    user.cards_opened = 0
    for key in data.PRESTIGE_RESET_KEYS:
        if hasattr(user, f"{key}_lvl"):
            setattr(user, f"{key}_lvl", 0)
    user.prestige_lvl = (user.prestige_lvl or 0) + 1
    await session.flush()
    bonus_pct = int(round((prestige_bonus(user) - 1.0) * 100))
    return True, f"Престиж {user.prestige_lvl}! Вечный бонус к доходу: +{bonus_pct}%."
