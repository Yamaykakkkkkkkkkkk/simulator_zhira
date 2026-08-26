from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import services
from ..keyboards import cards_page_kb, ikb, trade_accept_kb, trade_confirm_kb
from ..utils import edit_media, fmt

router = Router()

TRADES = {}
PICK_PAGE = 8


def _pick_pages(count: int) -> int:
    return max(1, (count + PICK_PAGE - 1) // PICK_PAGE)


async def _own_cards(session, user_id: int):
    from sqlalchemy import select

    from ..models import UserCard

    q = select(UserCard).where(UserCard.user_id == user_id).order_by(UserCard.id.desc())
    return (await session.scalars(q)).all()


@router.message(Command("trade"))
async def cmd_trade(message: Message, session):
    me = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Использование: /trade @<юзернейм_получателя> или /trade <ID_получателя>")
        return
    target = None
    raw = parts[1]
    if raw.startswith("@"):
        target = await services.get_by_username(session, raw)
    elif raw.isdigit():
        from ..models import User

        target = await session.get(User, int(raw))
    if target is None or target.id == me.id:
        await message.answer("❌ Игрок не найден.")
        return
    cards = await _own_cards(session, me.id)
    if not cards:
        await message.answer("❌ У вас нет жиров для обмена.")
        return
    TRADES[me.id] = {"target": target.id}
    pages = _pick_pages(len(cards))
    text = f"@{target.username or target.id}\nВыберите жир, который предложите на обмен:"
    await message.answer(
        text,
        reply_markup=cards_page_kb("trf", "trfp", cards[:PICK_PAGE], 0, pages, "trade_cancel"),
    )


@router.callback_query(lambda c: c.data == "trade_cancel")
async def cb_trade_cancel(cb: CallbackQuery):
    TRADES.pop(cb.from_user.id, None)
    await cb.answer("Обмен отменён")
    await edit_media(cb, None, "Обмен отменён.", None)


@router.callback_query(lambda c: c.data and c.data.startswith("trfp:"))
async def cb_trade_pick_page(cb: CallbackQuery, session):
    page = int(cb.data.split(":")[1])
    trade = TRADES.get(cb.from_user.id)
    if trade is None or "card" in trade:
        await cb.answer()
        return
    cards = await _own_cards(session, cb.from_user.id)
    pages = _pick_pages(len(cards))
    chunk = cards[page * PICK_PAGE : (page + 1) * PICK_PAGE]
    await cb.answer()
    await edit_media(
        cb,
        None,
        "Выберите жир, который предложите на обмен:",
        cards_page_kb("trf", "trfp", chunk, page, pages, "trade_cancel"),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("trf:"))
async def cb_trade_pick_card(cb: CallbackQuery, session):
    from sqlalchemy import select

    from ..models import UserCard

    card = await session.get(UserCard, int(cb.data.split(":")[1]))
    trade = TRADES.get(cb.from_user.id)
    if card is None or card.user_id != cb.from_user.id or trade is None:
        await cb.answer("Ошибка выбора.", show_alert=True)
        return
    if card.listed:
        await cb.answer("Этот жир выставлен на Авито.", show_alert=True)
        return
    trade["card"] = card.id
    target_id = trade["target"]
    from ..models import User

    tu = await session.get(User, target_id)
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"Предложение отправлено игроку @{tu.username or tu.id}. Ожидание ответа…",
        None,
    )
    try:
        await cb.bot.send_message(
            target_id,
            f"🤝 @{cb.from_user.username or cb.from_user.id} предлагает обмен:\n"
            f"Он отдаст: {card.name} ({card.weight} кг)\n"
            f"Вы отдадите один из своих жиров.",
            reply_markup=trade_accept_kb(cb.from_user.id),
        )
    except Exception:
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("tracc:"))
async def cb_trade_accept(cb: CallbackQuery, session):
    init_id = int(cb.data.split(":")[1])
    trade = TRADES.get(init_id)
    if trade is None or trade["target"] != cb.from_user.id or "card" not in trade:
        await cb.answer("Предложение уже неактуально.", show_alert=True)
        return
    cards = await _own_cards(session, cb.from_user.id)
    if not cards:
        await cb.answer("У вас нет жиров.", show_alert=True)
        return
    TRADES[cb.from_user.id] = {"with": init_id, "their_card": trade["card"]}
    pages = _pick_pages(len(cards))
    await cb.answer()
    await edit_media(
        cb,
        None,
        "Выберите свой жир для обмена:",
        cards_page_kb("trt", "trtp", cards[:PICK_PAGE], 0, pages, "trdec2"),
    )


@router.callback_query(lambda c: c.data == "trdec2")
async def cb_trade_decline_self(cb: CallbackQuery):
    t = TRADES.pop(cb.from_user.id, None)
    if t and "with" in t:
        TRADES.pop(t["with"], None)
    await cb.answer("Обмен отменён")
    await edit_media(cb, None, "Обмен отменён.", None)


@router.callback_query(lambda c: c.data and c.data.startswith("trdec:"))
async def cb_trade_decline(cb: CallbackQuery, session):
    init_id = int(cb.data.split(":")[1])
    trade = TRADES.pop(init_id, None)
    await cb.answer()
    await edit_media(cb, None, "Вы отказались от обмена.", None)
    if trade:
        try:
            await cb.bot.send_message(init_id, f"❌ Игрок отказался от обмена.")
        except Exception:
            pass


@router.callback_query(lambda c: c.data and c.data.startswith("trtp:"))
async def cb_trade_target_page(cb: CallbackQuery, session):
    page = int(cb.data.split(":")[1])
    t = TRADES.get(cb.from_user.id)
    if t is None or "picked" in t:
        await cb.answer()
        return
    cards = await _own_cards(session, cb.from_user.id)
    pages = _pick_pages(len(cards))
    chunk = cards[page * PICK_PAGE : (page + 1) * PICK_PAGE]
    await cb.answer()
    await edit_media(cb, None, "Выберите свой жир для обмена:", cards_page_kb("trt", "trtp", chunk, page, pages, "trdec2"))


@router.callback_query(lambda c: c.data and c.data.startswith("trt:"))
async def cb_trade_choose_theirs(cb: CallbackQuery, session):
    from ..models import UserCard

    card = await session.get(UserCard, int(cb.data.split(":")[1]))
    t = TRADES.get(cb.from_user.id)
    if card is None or card.user_id != cb.from_user.id or t is None:
        await cb.answer("Ошибка выбора.", show_alert=True)
        return
    if card.listed:
        await cb.answer("Этот жир выставлен на Авито.", show_alert=True)
        return
    t["picked"] = card.id
    their_card_id = t["their_card"]
    init_card = await session.get(UserCard, their_card_id)
    my_card = await session.get(UserCard, t["picked"])
    if init_card is None or my_card is None or init_card.user_id != t["with"]:
        await cb.answer("Жир инициатора больше недоступен.", show_alert=True)
        TRADES.pop(cb.from_user.id, None)
        TRADES.pop(t["with"], None)
        return
    await cb.answer()
    await edit_media(
        cb,
        None,
        f"Подтвердите обмен:\nВаш: {my_card.name} ({my_card.weight} кг)\n"
        f"На: {init_card.name} ({init_card.weight} кг)",
        trade_confirm_kb(),
    )


@router.callback_query(lambda c: c.data in ("tryes", "trno"))
async def cb_trade_finish(cb: CallbackQuery, session):
    from ..models import UserCard

    t = TRADES.get(cb.from_user.id)
    if t is None:
        await cb.answer("Обмен не найден.", show_alert=True)
        return
    init_id = t["with"]
    init_trade = TRADES.get(init_id)
    TRADES.pop(cb.from_user.id, None)
    if cb.data == "trno" or init_trade is None:
        TRADES.pop(init_id, None)
        await cb.answer()
        await edit_media(cb, None, "Обмен отменён.", None)
        try:
            await cb.bot.send_message(init_id, "❌ Обмен отменён.")
        except Exception:
            pass
        return
    a_card = await session.get(UserCard, init_trade["card"])
    b_card = await session.get(UserCard, t["picked"])
    if (
        a_card is None
        or b_card is None
        or a_card.user_id != init_id
        or b_card.user_id != cb.from_user.id
        or a_card.listed
        or b_card.listed
    ):
        TRADES.pop(init_id, None)
        await cb.answer("Обмен невозможен — карты изменились.", show_alert=True)
        return
    a_card.user_id, b_card.user_id = cb.from_user.id, init_id
    TRADES.pop(init_id, None)
    await cb.answer("✅ Обмен выполнен!")
    await edit_media(cb, None, f"✅ Обмен выполнен! Вы получили: {a_card.name} ({a_card.weight} кг)", None)
    try:
        await cb.bot.send_message(
            init_id, f"✅ Обмен выполнен! Вы получили: {b_card.name} ({b_card.weight} кг)"
        )
    except Exception:
        pass
