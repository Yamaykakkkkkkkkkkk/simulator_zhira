from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import data, services
from ..utils import fmt

router = Router()


@router.message(Command("level"))
async def cmd_level(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    info = services.player_level(user)
    xp = info["xp"]
    cur = info["xp_cur"]
    nxt = info["xp_next"]
    if nxt > cur:
        need = nxt - xp
        bar_len = 10
        filled = int((xp - cur) / max(1, (nxt - cur)) * bar_len)
        bar = "🟩" * filled + "⬜" * (bar_len - filled)
        progress = f"\n{bar}\nДо {info['next_lvl']} уровня: {fmt(need)} XP"
    else:
        progress = "\n🏆 MAX уровень!"
    text = (
        f"⭐ Уровень {info['lvl']}/50 — {info['title']}\n"
        f"✨ XP: {fmt(xp)} (уровень с {fmt(cur)} до {fmt(nxt)})"
        f"{progress}\n\n"
        f"Формула: cards*10 + upgrades*50 + sales*20 + casino_wins*30\n"
        f"🃏 Карты: {user.cards_opened} • ⬆️ Апгрейды: {user.upgrades_done} • "
        f"🤝 Продажи: {user.sales_done} • 🎰 Победы: {user.casino_wins}"
    )
    await message.answer(text)
