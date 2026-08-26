from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services
from ..keyboards import ikb
from ..utils import answer_media, edit_media, fmt

router = Router()


@router.message(Command("fexchange"))
async def cmd_exchange(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    text = (
        f"📊 Биржа F-Coin\n\n"
        f"Текущий курс: 1 F-Coin = 1,000,000 ФОчек\n"
        f"Комиссия при продаже: 5%\n\n"
        f"💼 Ваш портфель:\n"
        f"💠 F-Coins: {user.fcoins}\n"
        f"💰 ФОчки: {fmt(user.points)}\n\n"
        "Используйте кнопки ниже для торговли."
    )
    kb = ikb([
        [("📈 Купить 1 F-Coin", "exch_buy")],
        [("📉 Продать 1 F-Coin", "exch_sell")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data == "exch_buy")
async def cb_exchange_buy(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    if user.points < 1_000_000:
        await cb.answer("Недостаточно ФОчек. Нужно 1,000,000.", show_alert=True)
        return
    user.points -= 1_000_000
    user.fcoins += 1
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"✅ Куплен 1 F-Coin за 1,000,000 ФОчек.\n"
        f"💠 F-Coins: {user.fcoins}\n"
        f"💰 ФОчки: {fmt(user.points)}",
        None,
    )


@router.callback_query(lambda c: c.data == "exch_sell")
async def cb_exchange_sell(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    if user.fcoins < 1:
        await cb.answer("Недостаточно F-Coins.", show_alert=True)
        return
    user.fcoins -= 1
    payout = int(1_000_000 * 0.95)
    user.points += payout
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"✅ Продан 1 F-Coin за {fmt(payout)} ФОчек (с комиссией 5%).\n"
        f"💠 F-Coins: {user.fcoins}\n"
        f"💰 ФОчки: {fmt(user.points)}",
        None,
    )
