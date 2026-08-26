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

    lines = [
        f"@{user.username or user.id},",
        "Добро пожаловать в список квестов!\n",
        "📅 Еженедельные квесты",
        f"⏱ До обновления {remaining_str(weekly_left)}\n",
    ]
    for i, q in enumerate(data.WEEKLY_QUESTS, 1):
        lines.append(f"Квест №{i} ({fmt(q['reward'])} ФОчек)")
        lines.append(f"   {q['desc']}")
        lines.append("")

    lines.append("📆 Ежедневные квесты")
    lines.append(f"⏱ До обновления {remaining_str(daily_left)}\n")
    for i, q in enumerate(data.DAILY_QUESTS, 1):
        lines.append(f"Квест №{i} ({fmt(q['reward'])} ФОчек)")
        lines.append(f"   {q['desc']}")
        lines.append("")

    return "\n".join(lines)


@router.message(Command("fquests"))
async def cmd_quests(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    text = quests_text(user)
    kb = ikb([
        [("📥 Забрать награду за квест №1", "quest_claim:buy2")],
        [("📥 Забрать награду за квест №2", "quest_claim:casino1")],
        [("📥 Забрать награду за квест №3", "quest_claim:open5")],
        [("◀️ В меню", "noop")],
    ])
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

    reward = await services.claim_quest(session, user.id, quest_key)
    await edit_media(cb, None, f"✅ Награда получена: {fmt(reward)} ФОчек!")
