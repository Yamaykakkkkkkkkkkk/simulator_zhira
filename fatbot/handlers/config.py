from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services
from ..keyboards import ikb
from ..utils import edit_media

router = Router()


@router.message(Command("fconfig"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("⚙️ настройки", "настройки"))
async def cmd_config(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    no_cd = await services.cooldown_disabled(session)
    notifications = await services.get_user_setting(session, user.id, "notifications") or "on"

    text = (
        f"@{user.username or user.id},\n"
        "Выберите, что хотите настроить:\n\n"
        f"🔔 Уведомления: {'✅ Включены' if notifications == 'on' else '❌ Выключены'}\n"
        f"⏱ Кулдаун: {'❌ Отключен (для всех)' if no_cd else '✅ Активен'}\n"
    )
    kb = ikb([
        [("🔔 Уведомления", "cfg_notif")],
        [("📊 Статистика", "cfg_stats")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data == "cfg_notif")
async def cb_config_notifications(cb: CallbackQuery, session):
    current = await services.get_user_setting(session, cb.from_user.id, "notifications") or "on"
    new_val = "off" if current == "on" else "on"
    await services.set_user_setting(session, cb.from_user.id, "notifications", new_val)
    await cb.answer()
    status = "включены" if new_val == "on" else "выключены"
    await edit_media(cb, None, f"🔔 Уведомления {status}.", None)


@router.callback_query(lambda c: c.data == "cfg_stats")
async def cb_config_stats(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    stats = await services.collection_stats(session, user.id)
    await cb.answer()
    text = (
        f"📊 Ваша статистика:\n\n"
        f"🃏 Жиров: {stats['count']}\n"
        f"⚖️ Вес: {stats['weight']} кг\n"
        f"💰 Стоимость: {stats['value']:,} ФОчек\n"
        f"💵 Баланс: {user.points:,} ФОчек\n"
        f"💠 F-Coins: {user.fcoins}\n"
        f"🎰 Казино побед: {user.casino_wins}\n"
        f"⬆️ Апгрейдов: {user.upgrades_done}\n"
        f"🤝 Продаж: {user.sales_done}"
    )
    await edit_media(cb, None, text, None)
