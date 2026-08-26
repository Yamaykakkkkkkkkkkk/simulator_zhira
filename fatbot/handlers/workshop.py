from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import confirm_kb, workshop_kb
from ..utils import edit_media, fmt, remaining_str, utcnow

router = Router()


@router.message(Command("myworkshop"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🏪 мастерская", "мастерская"))
async def cmd_myworkshop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    if user.workshop_lvl == 0:
        await message.answer(
            f"@{user.username or user.id}, у Вас еще нет своей мастерской.\n"
            "Вы можете создать её, используя команду /newworkshop"
        )
        return
    await send_workshop_status(message, session, user)


@router.message(Command("newworkshop"))
async def cmd_newworkshop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    if user.workshop_lvl > 0:
        await message.answer("У вас уже есть мастерская! Используйте /myworkshop")
        return
    await message.answer(
        f"@{user.username or user.id},\n"
        "Вы хотите начать создание своей мастерской по переработке сала?\n"
        f"Создание будет стоить Вам {fmt(data.WORKSHOP_CREATE_COST)} ФОчек.",
        reply_markup=confirm_kb("wsnew_go"),
    )


@router.callback_query(lambda c: c.data == "wsnew_go")
async def cb_wsnew(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    if user.workshop_lvl > 0:
        await cb.answer("Уже создана.", show_alert=True)
        return
    if user.points < data.WORKSHOP_CREATE_COST:
        await cb.answer(f"Недостаточно ФОчек (нужно {fmt(data.WORKSHOP_CREATE_COST)}).", show_alert=True)
        return
    user.points -= data.WORKSHOP_CREATE_COST
    user.workshop_lvl = 1
    user.workshop_at = utcnow()
    await cb.answer()
    await edit_media(cb, None, "🏭 Мастерская построена! Доход капает каждый час. Не забывайте собирать его в /myworkshop")


def _status_text(user) -> str:
    pending = services.workshop_pending(user)
    income = services.workshop_income_hour(user)
    max_lvl = user.workshop_lvl >= data.WORKSHOP_MAX_LVL
    lines = [
        f"🏭 Ваша мастерская [ур. {user.workshop_lvl}/{data.WORKSHOP_MAX_LVL}]",
        f"📈 Доход: {fmt(income)} ФОчек/час (максимум за сутки: {fmt(income * 24)})",
    ]
    if max_lvl:
        lines.append("⬆️ Улучшение: MAX")
    else:
        lines.append(f"⬆️ Улучшение до ур. {user.workshop_lvl + 1}: {fmt(data.WORKSHOP_UPG_COST(user.workshop_lvl))} ФОчек")
    lines.append(f"\n💰 К сбору: {fmt(pending)} ФОчек")
    return "\n".join(lines)


async def send_workshop_status(message_or_cb, session, user):
    kb = workshop_kb(True)
    if hasattr(message_or_cb, "answer"):
        await message_or_cb.answer(_status_text(user), reply_markup=kb)
    else:
        await edit_media(message_or_cb, None, _status_text(user), kb)


@router.callback_query(lambda c: c.data == "wscol")
async def cb_wscollect(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    if user.workshop_lvl == 0:
        await cb.answer("Сначала создайте мастерскую.", show_alert=True)
        return
    amount = services.workshop_collect(user)
    await cb.answer()
    if amount <= 0:
        await edit_media(cb, None, "Пока нечего собирать. Загляните чуть позже!", workshop_kb(True))
        return
    achievements = await services.grant_achievements(session, user)
    text = f"💰 Собрано {fmt(amount)} ФОчек!\nБаланс: {fmt(user.points)}"
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await edit_media(cb, None, text, workshop_kb(True))


@router.callback_query(lambda c: c.data == "wsupg")
async def cb_wsupg(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    if user.workshop_lvl == 0:
        await cb.answer("Сначала создайте мастерскую.", show_alert=True)
        return
    if user.workshop_lvl >= data.WORKSHOP_MAX_LVL:
        await cb.answer("Максимальный уровень!", show_alert=True)
        return
    cost = data.WORKSHOP_UPG_COST(user.workshop_lvl)
    if user.points < cost:
        await cb.answer(f"Недостаточно ФОчек (нужно {fmt(cost)}).", show_alert=True)
        return
    user.points -= cost
    user.workshop_lvl += 1
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"✅ Мастерская улучшена до уровня {user.workshop_lvl}!\n📈 Новый доход: {fmt(services.workshop_income_hour(user))} ФОчек/час",
        workshop_kb(True),
    )
