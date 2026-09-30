from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media, fmt, remaining_str

router = Router()


def quests_text(user) -> str:
    from datetime import datetime, timedelta
    from ..utils import utcnow

    now = utcnow()
    daily_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    weekly_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = 7 - weekly_reset.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    weekly_reset += timedelta(days=days_ahead)

    daily_left = daily_reset - now
    weekly_left = weekly_reset - now

    # AGENT3 QUESTS: ротация — каждому юзеру 3 daily из 12 и 3 weekly из 10
    try:
        weekly_defs = services.get_user_weekly_quests(user.id)
    except Exception:
        weekly_defs = list(data.WEEKLY_QUESTS[:3])
    try:
        daily_defs = services.get_user_daily_quests(user.id)
    except Exception:
        daily_defs = list(data.DAILY_QUESTS[:3])

    lines = [
        f"@{user.username or user.id},",
        "Добро пожаловать в список квестов!\n",
        "📅 Еженедельные квесты",
        f"⏱ До обновления {remaining_str(weekly_left)}\n",
    ]
    for i, q in enumerate(weekly_defs, 1):
        fc = f" +{q.get('reward_fcoins')} FC" if q.get("reward_fcoins") else ""
        lines.append(f"Квест №{i} ({fmt(q['reward'])} ФОчек{fc})")
        lines.append(f"   {q['desc']}")
        lines.append("")

    lines.append("📆 Ежедневные квесты")
    lines.append(f"⏱ До обновления {remaining_str(daily_left)}\n")
    for i, q in enumerate(daily_defs, 1):
        fc = f" +{q.get('reward_fcoins')} FC" if q.get("reward_fcoins") else ""
        lines.append(f"Квест №{i} ({fmt(q['reward'])} ФОчек{fc})")
        lines.append(f"   {q['desc']}")
        lines.append("")

    return "\n".join(lines)


async def _daily_with_progress(session, user) -> list[dict]:
    """Ротация + квесты с ненулевым прогрессом, которых нет в ротации (чтобы прогресс был виден)."""
    defs = list(services.get_user_daily_quests(user.id))
    keys = {q["key"] for q in defs}
    try:
        progress_map = await services.get_user_quests_with_progress(session, user.id)
    except Exception:
        progress_map = {}
    daily_keys = {q["key"] for q in data.DAILY_QUESTS}
    for q in data.DAILY_QUESTS:
        if q["key"] not in keys and q["key"] in progress_map:
            defs.append(q)
    return defs


async def _weekly_with_progress(session, user) -> list[dict]:
    defs = list(services.get_user_weekly_quests(user.id))
    keys = {q["key"] for q in defs}
    try:
        progress_map = await services.get_user_quests_with_progress(session, user.id)
    except Exception:
        progress_map = {}
    for q in data.WEEKLY_QUESTS:
        if q["key"] not in keys and q["key"] in progress_map:
            defs.append(q)
    return defs


async def quests_text_full(session, user) -> str:
    from datetime import timedelta
    from ..utils import utcnow

    now = utcnow()
    daily_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    weekly_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_ahead = 7 - weekly_reset.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    weekly_reset += timedelta(days=days_ahead)
    daily_left = daily_reset - now
    weekly_left = weekly_reset - now

    weekly_defs = await _weekly_with_progress(session, user)
    daily_defs = await _daily_with_progress(session, user)

    lines = [
        f"@{user.username or user.id},",
        "Добро пожаловать в список квестов!\n",
        "📅 Еженедельные квесты",
        f"⏱ До обновления {remaining_str(weekly_left)}\n",
    ]
    for i, q in enumerate(weekly_defs, 1):
        prog = await services.get_quest_progress(session, user.id, q["key"])
        p = f"{prog.progress}/{prog.target}" if prog else f"0/{q['target']}"
        mark = "✅" if (prog and prog.completed and not prog.claimed) else ("🎁" if (prog and prog.claimed) else "⬜")
        fc = f" +{q.get('reward_fcoins')} FC" if q.get("reward_fcoins") else ""
        lines.append(f"{mark} Квест №{i} ({fmt(q['reward'])} ФОчек{fc}) [{p}]")
        lines.append(f"   {q['desc']}")
        lines.append("")

    lines.append("📆 Ежедневные квесты")
    lines.append(f"⏱ До обновления {remaining_str(daily_left)}\n")
    for i, q in enumerate(daily_defs, 1):
        prog = await services.get_quest_progress(session, user.id, q["key"])
        p = f"{prog.progress}/{prog.target}" if prog else f"0/{q['target']}"
        mark = "✅" if (prog and prog.completed and not prog.claimed) else ("🎁" if (prog and prog.claimed) else "⬜")
        fc = f" +{q.get('reward_fcoins')} FC" if q.get("reward_fcoins") else ""
        lines.append(f"{mark} Квест №{i} ({fmt(q['reward'])} ФОчек{fc}) [{p}]")
        lines.append(f"   {q['desc']}")
        lines.append("")
    lines.append("⭐ Уровень: /level  •  📖 Сюжет: /story  •  ❄️ Сезон: /season")
    return "\n".join(lines)


def _active_keys(user_id: int) -> list[str]:
    try:
        d = [q["key"] for q in services.get_user_daily_quests(user_id)]
    except Exception:
        d = [q["key"] for q in data.DAILY_QUESTS[:3]]
    try:
        w = [q["key"] for q in services.get_user_weekly_quests(user_id)]
    except Exception:
        w = [q["key"] for q in data.WEEKLY_QUESTS[:3]]
    return w + d


async def _active_keys_full(session, user) -> list[str]:
    """Ключи для кнопок: ротация + квесты с ненулевым прогрессом (чтобы их можно было забрать)."""
    keys = _active_keys(user.id)
    try:
        progress_map = await services.get_user_quests_with_progress(session, user.id)
    except Exception:
        return keys
    for k in progress_map:
        if k not in keys:
            keys.append(k)
    return keys


@router.message(Command("fquests"))
async def cmd_quests(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    try:
        await services.purge_stale_quests(session)
    except Exception:
        pass
    try:
        text = await quests_text_full(session, user)
    except Exception:
        text = quests_text(user)
    keys = await _active_keys_full(session, user)
    rows = [[(f"📥 Забрать: {k}", f"quest_claim:{k}")] for k in keys]
    rows.append([("📥 Забрать всё", "quest_claim_all")])
    rows.append([("◀️ В меню", "noop")])
    kb = ikb(rows)
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("quest_claim:"))
async def cb_quest_claim(cb: CallbackQuery, session):
    quest_key = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    quest = await services.get_quest_progress(session, user.id, quest_key)
    await cb.answer()
    if quest is None:
        await edit_media(cb, None, "❌ Квест не найден. Сыграйте сначала!", None)
        return
    if not quest.completed:
        await edit_media(cb, None, f"❌ Квест ещё не выполнен! Прогресс: {quest.progress}/{quest.target}", None)
        return
    if quest.claimed:
        await edit_media(cb, None, "✅ Награда уже получена!", None)
        return

    fc = quest.reward_fcoins or 0
    reward = await services.claim_quest(session, user.id, quest_key)
    extra = f" +{fc} FC" if fc else ""
    await edit_media(cb, None, f"✅ Награда получена: {fmt(reward)} ФОчек{extra}!")


# AGENT3 QUESTS: забрать всё
@router.callback_query(lambda c: c.data == "quest_claim_all")
async def cb_quest_claim_all(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    keys = await _active_keys_full(session, user)
    claimed, pts, fcs = await services.claim_all_quests(session, user.id, keys)
    await cb.answer()
    if not claimed:
        await edit_media(cb, None, "❌ Нет готовых к выдаче наград. Выполните квесты из /fquests!", None)
        return
    extra = f" +{fcs} FC" if fcs else ""
    await edit_media(cb, None, f"✅ Забрано квестов: {len(claimed)} ({', '.join(claimed)})\n💰 +{fmt(pts)} ФОчек{extra}!")
