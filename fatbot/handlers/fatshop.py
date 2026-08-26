from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import answer_media, edit_media, fmt

router = Router()


@router.message(Command("fatshop"))
async def cmd_fatshop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    text = (
        f"@{user.username or user.id}\n"
        "Добро пожаловать в магазин жиров!\n\n"
        "Выберите редкость жира:"
    )
    rows = []
    for key in data.ORDER:
        d = data.RARITIES[key]
        price = data.FATSHOP_PRICES.get(key, 1000)
        rows.append([(f"{d['emoji']} {d['name']} — {fmt(price)} ФОчек", f"fatshop:{key}")])
    rows.append([("◀️ В меню", "noop")])
    await message.answer(text, reply_markup=ikb(rows))


@router.callback_query(lambda c: c.data and c.data.startswith("fatshop:"))
async def cb_fatshop_rarity(cb: CallbackQuery, session):
    rarity = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    d = data.RARITIES.get(rarity)
    if d is None:
        await cb.answer("Редкость не найдена.", show_alert=True)
        return
    price = data.FATSHOP_PRICES.get(rarity, 1000)
    text = (
        f"{d['emoji']} {d['name']}\n"
        f"Цена: {fmt(price)} ФОчек\n"
        f"Вес: {d['min']}-{d['max']} кг\n\n"
        "Нажмите «Купить», чтобы получить случайный жир этой редкости."
    )
    kb = ikb([
        [(f"🛒 Купить за {fmt(price)} ФОчек", f"fatshop_buy:{rarity}")],
        [("◀️ Назад", "fatshop_back")],
    ])
    await cb.answer()
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data == "fatshop_back")
async def cb_fatshop_back(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    text = f"@{user.username or user.id}\nДобро пожаловать в магазин жиров!\n\nВыберите редкость жира:"
    rows = []
    for key in data.ORDER:
        d = data.RARITIES[key]
        price = data.FATSHOP_PRICES.get(key, 1000)
        rows.append([(f"{d['emoji']} {d['name']} — {fmt(price)} ФОчек", f"fatshop:{key}")])
    rows.append([("◀️ В меню", "noop")])
    await cb.answer()
    await edit_media(cb, None, text, ikb(rows))


@router.callback_query(lambda c: c.data and c.data.startswith("fatshop_buy:"))
async def cb_fatshop_buy(cb: CallbackQuery, session):
    rarity = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")

    d = data.RARITIES.get(rarity)
    names = data.NAMES.get(rarity, ["Жир"])
    import random
    card_name = random.choice(names)

    card, error = await services.buy_fatshop_card(session, user, rarity, card_name)
    if error:
        await cb.answer(error, show_alert=True)
        return

    await services.update_quest_progress(session, user.id, "buy2")
    await services.update_quest_progress(session, user.id, "buy20")
    achievements = await services.grant_achievements(session, user)

    d = data.RARITIES[card.rarity]
    text = (
        f"🎉 Вы купили жир!\n\n"
        f"{d['emoji']} {card.name}\n"
        f"{d['name']} | Вес: {card.weight} кг\n"
        f"Цена: {fmt(card.base_price)} ФОчек\n"
    )
    if card.defects:
        text += f"Дефекты: {', '.join(card.defects)}\n"
    text += f"\n💰 Остаток: {fmt(user.points)} ФОчек"
    if achievements:
        text += "\n\n🏆 " + "\n🏆 ".join(achievements)
    await cb.answer()
    await edit_media(cb, None, text, None)
