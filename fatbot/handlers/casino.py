import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import bets_kb, casino_kb
from ..utils import edit_media, fmt

router = Router()


@router.message(Command("casino"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🎰 казино", "казино"))
async def cmd_casino(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    text = (
        "Добро пожаловать в Fat Casino! 🎰\nИспытай свою удачу!\n\n"
        f"💰 Ваш баланс: {fmt(user.points)} ФОчек"
    )
    await message.answer(text, reply_markup=casino_kb())


@router.callback_query(lambda c: c.data == "casino_menu")
async def cb_casino_menu(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"Добро пожаловать в Fat Casino! 🎰\n\n💰 Баланс: {fmt(user.points)} ФОчек",
        casino_kb(),
    )


@router.callback_query(lambda c: c.data == "cas_cf")
async def cb_coinflip_menu(cb: CallbackQuery):
    await cb.answer()
    await edit_media(cb, None, "🪙 Монетка: угадаете сторону — удвоение ставки!\nВыберите ставку:", bets_kb("cf"))


@router.callback_query(lambda c: c.data == "cas_sl")
async def cb_slots_menu(cb: CallbackQuery):
    await cb.answer()
    await edit_media(
        cb,
        None,
        "🎰 Слоты: 3 одинаковых — x12, пара — x2!\nВыберите ставку:",
        bets_kb("sl"),
    )


async def _place_bet(cb: CallbackQuery, session) -> tuple | None:
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    raw = cb.data.split(":")[1]
    if raw == "all":
        bet = user.points
    else:
        bet = int(raw)
    if bet < data.CASINO_MIN_BET:
        await cb.answer(f"Минимальная ставка: {data.CASINO_MIN_BET:,}", show_alert=True)
        return None
    if bet > data.CASINO_MAX_BET:
        bet = data.CASINO_MAX_BET
    if bet <= 0 or user.points < bet:
        await cb.answer("Недостаточно ФОчек.", show_alert=True)
        return None
    return user, bet


@router.callback_query(lambda c: c.data and c.data.startswith("cf:"))
async def cb_coinflip(cb: CallbackQuery, session):
    placed = await _place_bet(cb, session)
    if placed is None:
        return
    user, bet = placed
    edge = await services.casino_edge(session, user)
    user.points -= bet
    win = await services.coinflip_win(random, edge)
    side = random.choice(["Орёл", "Решка"])
    if win:
        user.points += bet * 2
        user.casino_wins += 1
        text = f"🪙 Выпал {side} — вы выиграли {fmt(bet)} ФОчек!\n💰 Баланс: {fmt(user.points)}"
    else:
        text = f"🪙 Выпал {side} — вы проиграли {fmt(bet)} ФОчек.\n💰 Баланс: {fmt(user.points)}"
    achievements = await services.grant_achievements(session, user)
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await cb.answer()
    await edit_media(cb, None, text, bets_kb("cf"))


@router.callback_query(lambda c: c.data and c.data.startswith("sl:"))
async def cb_slots(cb: CallbackQuery, session):
    placed = await _place_bet(cb, session)
    if placed is None:
        return
    user, bet = placed
    user.points -= bet
    reels, mult = services.spin_slots(random)
    payout = int(bet * mult)
    if payout > 0:
        user.points += payout
        user.casino_wins += 1
    result = (
        f"🎉 Джекпот! Выигрыш {fmt(payout - bet)} ФОчек!"
        if mult >= 12
        else (f"✅ Пара! Выигрыш {fmt(payout - bet)} ФОчек." if mult > 0 else f"😢 Вы проиграли {fmt(bet)} ФОчек.")
    )
    achievements = await services.grant_achievements(session, user)
    text = (
        "🎰 [ " + " | ".join(reels) + " ]\n\n"
        + result
        + f"\n💰 Баланс: {fmt(user.points)} ФОчек"
    )
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await cb.answer()
    await edit_media(cb, None, text, bets_kb("sl"))
