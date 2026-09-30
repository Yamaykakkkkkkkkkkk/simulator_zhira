from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media, fmt

router = Router()


@router.message(Command("season"))
async def cmd_season(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    ev = data.SEASON_EVENT
    active = services.is_season_active()
    status = "🟢 Активен" if active else "⚪ Неактивен"
    text = (
        f"{ev['name']}\n{status}\n"
        f"📅 {ev['start']} — {ev['end']}\n"
        f"{ev['desc']}\n\n"
        f"🎁 Бонус: x{ev['multiplier']} к daily (≈{fmt(max(ev['bonus'], data.DAILY_REWARDS[0] * ev['multiplier']))} ФОчек), 1 раз за сезон."
    )
    kb = ikb([
        [("🎁 Забрать сезонный бонус", "season_claim")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data == "season_claim")
async def cb_season_claim(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    amount, err = await services.claim_season_bonus(session, user)
    await cb.answer()
    if err:
        await edit_media(cb, None, f"❌ {err}", None)
        return
    await edit_media(cb, None, f"✅ Сезонный бонус получен: +{fmt(amount)} ФОчек! ❄️", None)
