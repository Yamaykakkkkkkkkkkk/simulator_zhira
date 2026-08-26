from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media, fmt

router = Router()


@router.message(Command("fauction"))
async def cmd_auction(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    text = (
        "Добро пожаловать в меню аукционов! 💸\n"
        "Здесь вы можете посоревноваться с другими игроками за коллекционный жир.\n\n"
        "Выберите действие:"
    )
    kb = ikb([
        [("📜 Текущие аукционы", "auc_list")],
        [("📤 Выставить на аукцион", "auc_sell")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data == "auc_list")
async def cb_auc_list(cb: CallbackQuery, session):
    from ..models import Auction, UserCard, User
    from sqlalchemy import select

    auctions = (
        await session.scalars(
            select(Auction).where(Auction.ends_at > services.utcnow()).order_by(Auction.ends_at)
        )
    ).all()

    if not auctions:
        await cb.answer()
        await edit_media(cb, None, "📜 Пока нет активных аукционов.", None)
        return

    lines = ["📜 Активные аукционы:\n"]
    for a in auctions[:10]:
        card = await session.get(UserCard, a.card_id)
        seller = await session.get(User, a.seller_id)
        if card:
            d = data.RARITIES.get(card.rarity, {})
            lines.append(
                f"#{a.id} {d.get('emoji', '🐷')} {card.name}\n"
                f"   Ставка: {fmt(a.current_bid)} ФОчек\n"
                f"   Продавец: @{seller.username if seller else '?'}\n"
            )

    await cb.answer()
    await edit_media(cb, None, "\n".join(lines), None)
