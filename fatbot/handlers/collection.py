from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import cards_page_kb, card_manage_kb, ikb, rarities_kb
from ..utils import edit_media, fmt

router = Router()

PAGE_SIZE = 8


def detail_text(user, card) -> str:
    d = data.RARITIES[card.rarity]
    lines = [
        f"{d['emoji']} {card.name}",
        f"Редкость: {d['name']}",
        f"Вес: {fmt(card.weight)} кг",
        f"Цена: {fmt(card.base_price)} ФОчек",
    ]
    if card.defects:
        lines.append("Дефекты: " + ", ".join(card.defects))
    if card.listed:
        lines.append("\n🔖 Выставлен на Авито")
    return "\n".join(lines)


@router.message(Command("myfats"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🎒 коллекция", "мои жиры"))
async def cmd_myfats(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    stats = await services.collection_stats(session, user.id)
    if stats["count"] == 0:
        await message.answer(f"@{user.username or user.id}, ваша коллекция пуста. Напишите «ФКарточка», чтобы выбить первого жира!")
        return
    text = (
        f"@{user.username or user.id}, выберите категорию ваших жиров:\n\n"
        f"🃏 Всего: {stats['count']} | ⚖️ {fmt(stats['weight'])} кг | 💰 {fmt(stats['value'])} ФОчек"
    )
    await message.answer(text, reply_markup=rarities_kb("coll", stats["by_rarity"], back_cb="noop"))


@router.callback_query(lambda c: c.data == "coll_root")
async def cb_coll_root(cb: CallbackQuery, session):
    stats = await services.collection_stats(session, cb.from_user.id)
    await cb.answer()
    if stats["count"] == 0:
        await edit_media(cb, "profile", "Ваша коллекция пуста.")
        return
    await edit_media(
        cb,
        "collection",
        "Выберите категорию ваших жиров:",
        rarities_kb("coll", stats["by_rarity"], back_cb="noop"),
    )


def _pages(count: int) -> int:
    return max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)


async def _rarity_page_payload(session, user_id: int, rarity: str, page: int):
    from sqlalchemy import func, select

    from ..models import UserCard

    base = select(UserCard).where(UserCard.user_id == user_id, UserCard.rarity == rarity)
    total = (await session.scalar(select(func.count()).select_from(base.subquery()))) or 0
    pages = _pages(total)
    page = max(0, min(page, pages - 1))
    q = base.order_by(UserCard.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE)
    cards = (await session.scalars(q)).all()
    d = data.RARITIES[rarity]
    text = f"{d['emoji']} {d['name']} — {total} шт."
    return cards, page, pages, text


@router.callback_query(lambda c: c.data and c.data.startswith("coll:"))
async def cb_coll_rarity(cb: CallbackQuery, session):
    parts = cb.data.split(":")
    rarity = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    cards, page, pages, text = await _rarity_page_payload(session, cb.from_user.id, rarity, page)
    await cb.answer()
    kb = cards_page_kb("card", f"coll:{rarity}", cards, page, pages, "coll_root")
    await edit_media(cb, "collection", text or "Пусто", kb)


@router.callback_query(lambda c: c.data and c.data.startswith("card:"))
async def cb_card_detail(cb: CallbackQuery, session):
    from ..models import UserCard

    card_id = int(cb.data.split(":")[1])
    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != cb.from_user.id:
        await cb.answer("Карта не найдена.", show_alert=True)
        return
    await cb.answer()
    await edit_media(cb, "card", detail_text(None, card), card_manage_kb(card.id, card.listed))
