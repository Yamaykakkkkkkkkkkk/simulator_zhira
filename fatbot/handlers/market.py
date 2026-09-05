from sqlalchemy import func, select

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import cards_page_kb, ikb, market_nav_kb
from ..models import MarketListing, User, UserCard
from ..utils import answer_media, edit_media, fmt

router = Router()

PAGE_SIZE = 5
PENDING_PRICE = {}


def listing_text(l: MarketListing, card: UserCard, seller: User | None) -> str:
    d = data.RARITIES[card.rarity]
    defects = ", ".join(card.defects) if card.defects else "(пусто)"
    seller_name = f"@{seller.username}" if seller and seller.username else (str(l.seller_id) if not seller else f"ID {l.seller_id}")
    return (
        f"Oбъявление №{l.id}\n"
        f"{d['emoji']} {card.name} | {d['name']}\n"
        f"Описание: {defects}\n"
        f"Цена: {fmt(l.price)} ФОчек\n"
        f"Продавец: {seller_name}\n"
    )


@router.message(Command("avito"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("📢 авито", "авито"))
async def cmd_avito(message: Message, session):
    await send_market_page(message, session, 0)


async def send_market_page(message_or_cb, session, page: int):
    total = (
        await session.scalar(
            select(func.count()).select_from(select(MarketListing).where(MarketListing.active == True).subquery())  # noqa: E712
        )
    ) or 0
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    listings = (
        await session.scalars(
            select(MarketListing)
            .where(MarketListing.active == True)  # noqa: E712
            .order_by(MarketListing.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).all()
    blocks = [
        "Добро пожаловать на ЖироАвито!\n",
        "Сортировка: Сначала новое\nФильтры: не установлены\n",
    ]
    ids = []
    if not listings:
        blocks.append("\nПока никто ничего не продаёт. Станьте первым — 📤 Выставить жир!")
    for l in listings:
        card = await session.get(UserCard, l.card_id)
        seller = await session.get(User, l.seller_id)
        blocks.append(listing_text(l, card, seller))
        ids.append(l.id)
    kb = market_nav_kb(page, pages, ids)
    text = "\n".join(blocks)
    if isinstance(message_or_cb, Message):
        await answer_media(message_or_cb, "avito", text[:4000], kb)
    else:
        await edit_media(message_or_cb, "avito", text[:4000], kb)


@router.callback_query(lambda c: c.data and c.data.startswith("avp:"))
async def cb_avito_page(cb: CallbackQuery, session):
    await cb.answer()
    await send_market_page(cb, session, int(cb.data.split(":")[1]))


@router.callback_query(lambda c: c.data == "avito_menu")
async def cb_avito_menu(cb: CallbackQuery, session):
    await cb.answer()
    await send_market_page(cb, session, 0)


@router.message(Command("avisell"))
async def cmd_avisell(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    cards = list(
        (
            await session.scalars(
                select(UserCard).where(UserCard.user_id == user.id, UserCard.listed == False).order_by(UserCard.id.desc())  # noqa: E712
            )
        ).all()
    )
    if not cards:
        await message.answer("У вас нет жиров для продажи.")
        return
    chunk = cards[:8]
    await message.answer(
        "📤 Выберите жир для выставления на Авито:",
        reply_markup=cards_page_kb("avpick", "avselp", chunk, 0, max(1, (len(cards) + 7) // 8), "noop"),
    )


@router.callback_query(lambda c: c.data == "avsell_menu")
async def cb_avsell_menu(cb: CallbackQuery, session):
    cards = list(
        (
            await session.scalars(
                select(UserCard).where(UserCard.user_id == cb.from_user.id, UserCard.listed == False).order_by(UserCard.id.desc())  # noqa: E712
            )
        ).all()
    )
    if not cards:
        await cb.answer("У вас нет жиров для продажи.", show_alert=True)
        return
    await cb.answer()
    await edit_media(
        cb,
        None,
        "📤 Выберите жир для выставления на Авито:",
        cards_page_kb("avpick", "avselp", cards[:8], 0, max(1, (len(cards) + 7) // 8), "avito_menu"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("avselp:"))
async def cb_avsell_page(cb: CallbackQuery, session):
    page = int(cb.data.split(":")[1])
    cards = list(
        (
            await session.scalars(
                select(UserCard).where(UserCard.user_id == cb.from_user.id, UserCard.listed == False).order_by(UserCard.id.desc())  # noqa: E712
            )
        ).all()
    )
    chunk = cards[page * 8 : (page + 1) * 8]
    await cb.answer()
    await edit_media(
        cb,
        None,
        "📤 Выберите жир для выставления на Авито:",
        cards_page_kb("avpick", "avselp", chunk, page, max(1, (len(cards) + 7) // 8), "avito_menu"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("avpick:"))
async def cb_avpick(cb: CallbackQuery, session):
    card = await session.get(UserCard, int(cb.data.split(":")[1]))
    if card is None or card.user_id != cb.from_user.id or card.listed:
        await cb.answer("Недоступно.", show_alert=True)
        return
    PENDING_PRICE[cb.from_user.id] = card.id
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"Выставляем «{card.name}» ({card.weight} кг).\nОтправьте цену числом (в ФОчках):",
        ikb([[("❌ Отмена", "avcancel_price")]]),
    )


@router.callback_query(lambda c: c.data == "avcancel_price")
async def cb_avcancel_price(cb: CallbackQuery):
    PENDING_PRICE.pop(cb.from_user.id, None)
    await cb.answer("Отменено")
    await edit_media(cb, None, "Отменено.", None)


@router.message(Command("avimy"))
async def cmd_avimy(message: Message, session):
    rows = await my_listings(session, message.from_user.id)
    await message.answer(rows[0], reply_markup=rows[1])


async def my_listings(session, user_id: int):
    listings = (
        await session.scalars(
            select(MarketListing).where(MarketListing.seller_id == user_id, MarketListing.active == True).order_by(MarketListing.id.desc())  # noqa: E712
        )
    ).all()
    if not listings:
        return "У вас нет активных объявлений.", None
    lines = ["📦 Ваши активные объявления:\n"]
    buttons = []
    for l in listings:
        card = await session.get(UserCard, l.card_id)
        lines.append(f"№{l.id} — {card.name} · {fmt(l.price)} ФОчек")
        buttons.append([(f"❌ Снять №{l.id}", f"avcancel:{l.id}")])
    buttons.append([("◀️ В меню", "noop")])
    return "\n".join(lines), ikb(buttons)


@router.callback_query(lambda c: c.data == "avimy")
async def cb_avimy(cb: CallbackQuery, session):
    text, kb = await my_listings(session, cb.from_user.id)
    await cb.answer()
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data and c.data.startswith("avcancel:"))
async def cb_avcancel(cb: CallbackQuery, session):
    lid = int(cb.data.split(":")[1])
    l = await session.get(MarketListing, lid)
    if l is None or l.seller_id != cb.from_user.id or not l.active:
        await cb.answer("Объявление не найдено.", show_alert=True)
        return
    l.active = False
    card = await session.get(UserCard, l.card_id)
    if card:
        card.listed = False
    await cb.answer("Объявление снято")
    text, kb = await my_listings(session, cb.from_user.id)
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data and c.data.startswith("avbuy:"))
async def cb_avbuy(cb: CallbackQuery, session):
    lid = int(cb.data.split(":")[1])
    l = await session.get(MarketListing, lid)
    if l is None or not l.active:
        await cb.answer("Объявление уже неактуально.", show_alert=True)
        return
    if l.seller_id == cb.from_user.id:
        await cb.answer("Это ваше объявление!", show_alert=True)
        return
    buyer = await services.get_or_create_user(session, cb.from_user.id, cb.from_user.username, cb.from_user.full_name)
    if buyer.points < l.price:
        await cb.answer("Недостаточно ФОчек.", show_alert=True)
        return
    card = await session.get(UserCard, l.card_id)
    if card is None or card.listed is False:
        await cb.answer("Жир недоступен.", show_alert=True)
        return
    seller = await session.get(User, l.seller_id)
    buyer.points -= l.price
    seller.points += int(l.price * (1 - data.MARKET_FEE))
    card.user_id = buyer.id
    card.listed = False
    l.active = False
    buyer.sales_done += 1
    achievements = await services.grant_achievements(session, buyer)
    fee_note = int(l.price * data.MARKET_FEE)
    await cb.answer("✅ Куплено!")
    text = (
        f"✅ Вы купили «{card.name}» ({card.weight} кг) за {fmt(l.price)} ФОчек.\n"
        f"(Продавец получил {fmt(int(l.price * (1 - data.MARKET_FEE)))}, комиссия {fmt(fee_note)})"
    )
    if achievements:
        text += "\n🏆 " + "\n🏆 ".join(achievements)
    await edit_media(cb, None, text, None)
    try:
        await cb.bot.send_message(
            seller.id,
            f"💰 Ваше объявление №{lid} куплено! Вам начислено {fmt(int(l.price * (1 - data.MARKET_FEE)))} ФОчек.",
        )
    except Exception:
        pass


@router.message(lambda m: m.from_user and m.from_user.id in PENDING_PRICE and m.text and m.text.isdigit())
async def handle_listing_price(message: Message, session):
    card_id = PENDING_PRICE.pop(message.from_user.id)
    price = int(message.text)
    if price <= 0 or price > 100_000_000_000:
        await message.answer("❌ Некорректная цена. Попробуйте ещё раз: /avisell")
        return
    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != message.from_user.id or card.listed:
        await message.answer("❌ Жир недоступен.")
        return
    existing = (
        await session.scalars(select(MarketListing).where(MarketListing.card_id == card.id, MarketListing.active == True))  # noqa: E712
    ).first()
    if existing:
        await message.answer("❌ Уже выставлено.")
        return
    listing = MarketListing(card_id=card.id, seller_id=message.from_user.id, price=price)
    session.add(listing)
    card.listed = True
    await session.flush()
    await message.answer(
        f"✅ Объявление №{listing.id or ''} создано!\n"
        f"«{card.name}» ({card.weight} кг) за {fmt(price)} ФОчек.\n"
        f"Комиссия при продаже: {int(data.MARKET_FEE * 100)}%."
    )
