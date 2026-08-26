from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb, rarities_kb
from ..models import UserCard
from ..services import sell_cards
from ..utils import edit_media, fmt

router = Router()


@router.message(Command("sellall"))
@router.message(lambda m: m.text and m.text.strip().lower() == "продать всех")
async def cmd_sellall(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    stats = await services.collection_stats(session, user.id)
    if stats["count"] == 0:
        await message.answer("У вас нет жиров для продажи.")
        return
    text = f"@{user.username or user.id},\nВыберите редкость тех жиров, которые вы хотите продать."
    await message.answer(text, reply_markup=rarities_kb("selr", stats["by_rarity"], back_cb="noop"))


@router.callback_query(lambda c: c.data and c.data.startswith("selr:"))
async def cb_sellall_pick(cb: CallbackQuery):
    rarity = cb.data.split(":")[1]
    d = data.RARITIES[rarity]
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"Продать всех жиров редкости «{d['name']}»?\nДеньги придут сразу после подтверждения.",
        ikb([[("✅ Продать", f"selall_go:{rarity}"), ("❌ Отмена", "noop")]]),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("sellone:"))
async def cb_sell_one(cb: CallbackQuery, session):
    card_id = int(cb.data.split(":")[1])
    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != cb.from_user.id:
        await cb.answer("Жир не найден.", show_alert=True)
        return
    if card.listed:
        await cb.answer("Жир выставлен на Авито. Сначала снимите объявление.", show_alert=True)
        return
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    price_before = card.base_price
    total = await sell_cards(session, user, [card])
    achievements = await services.grant_achievements(session, user)
    text = f"💸 Жир «{card.name}» продан за {fmt(total)} ФОчек."
    if total != price_before:
        pass
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await cb.answer()
    await edit_media(cb, None, text, None)


@router.callback_query(lambda c: c.data and c.data.startswith("selall_go:"))
async def cb_sellall_go(cb: CallbackQuery, session):
    rarity = cb.data.split(":")[1]
    from sqlalchemy import select

    cards = list(
        (
            await session.scalars(
                select(UserCard).where(UserCard.user_id == cb.from_user.id, UserCard.rarity == rarity,
                                       UserCard.listed == False)  # noqa: E712
            )
        ).all()
    )
    if not cards:
        await cb.answer("Нет жиров этой редкости.", show_alert=True)
        return
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    total = await sell_cards(session, user, cards)
    achievements = await services.grant_achievements(session, user)
    text = (
        f"💸 Продано {len(cards)} жиров ({data.RARITIES[rarity]['name']}) за {fmt(total)} ФОчек.\n"
        f"💰 Баланс: {fmt(user.points)} ФОчек"
    )
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await cb.answer()
    await edit_media(cb, None, text, None)
