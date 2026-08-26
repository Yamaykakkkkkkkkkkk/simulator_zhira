from sqlalchemy import select

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import cards_page_kb, ikb
from ..models import UserCard
from ..utils import edit_media, fmt

router = Router()

PAGE = 8


async def _cards_of_rarity(session, user_id: int, rarity: str, exclude_listed=False):
    q = select(UserCard).where(UserCard.user_id == user_id, UserCard.rarity == rarity)
    if exclude_listed:
        q = q.where(UserCard.listed == False)  # noqa: E712
    return list((await session.scalars(q)).all())


@router.message(Command("upgrade"))
async def cmd_upgrade(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    stats = await services.collection_stats(session, user.id)
    upgradable = {k: v for k, v in stats["by_rarity"].items() if k != "mythic"}
    if not upgradable:
        await message.answer("У вас нет жиров для улучшения.")
        return
    luck = await services.luck_bonus(session, user)
    text = (
        f"@{user.username or user.id}\n"
        "📋 Выберите редкость жира, которую хотите улучшить. В скобках указан ваш шанс на успех."
    )
    rows = []
    for key in data.ORDER[:-1]:
        cnt = upgradable.get(key, 0)
        if not cnt:
            continue
        chance = int(services.upgrade_chance(key, luck) * 100)
        fee = data.UPGRADE_FEE[key]
        d = data.RARITIES[key]
        rows.append([(f"{d['emoji']} {d['name']} ({chance}%) — комиссия {fee:,}", f"upr:{key}")])
    if not rows:
        await message.answer("У вас нет жиров для улучшения.")
        return
    rows.append([("◀️ В меню", "noop")])
    await message.answer(text, reply_markup=ikb(rows))


async def _upgrade_pick_page(cb: CallbackQuery, session, rarity: str, page: int):
    cards = await _cards_of_rarity(session, cb.from_user.id, rarity)
    pages = max(1, (len(cards) + PAGE - 1) // PAGE)
    chunk = cards[page * PAGE : (page + 1) * PAGE]
    d = data.RARITIES[rarity]
    fee = data.UPGRADE_FEE[rarity]
    text = f"{d['emoji']} {d['name']} — выберите жир (комиссия за попытку: {fee:,} ФОчек):"
    kb = cards_page_kb("upgo", f"upl:{rarity}", chunk, page, pages, f"upr_back")
    return text, kb


@router.callback_query(lambda c: c.data and c.data.startswith("upr:"))
async def cb_upgrade_rarity(cb: CallbackQuery, session):
    rarity = cb.data.split(":")[1]
    text, kb = await _upgrade_pick_page(cb, session, rarity, 0)
    await cb.answer()
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data and c.data.startswith("upl:"))
async def cb_upgrade_page(cb: CallbackQuery, session):
    _, rarity, page = cb.data.split(":")
    text, kb = await _upgrade_pick_page(cb, session, rarity, int(page))
    await cb.answer()
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data == "upr_back")
async def cb_upr_back(cb: CallbackQuery):
    await cb.answer()
    await edit_media(cb, None, "Используйте /upgrade заново.", None)


@router.callback_query(lambda c: c.data and c.data.startswith("upone:"))
async def cb_upgrade_confirm(cb: CallbackQuery, session):
    from sqlalchemy import select as _s

    card_id = int(cb.data.split(":")[1])
    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != cb.from_user.id:
        await cb.answer("Жир не найден.", show_alert=True)
        return
    if card.rarity == "mythic":
        await cb.answer("Легендарный жир улучшить нельзя!", show_alert=True)
        return
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    chance = int(services.upgrade_chance(card.rarity, await services.luck_bonus(session, user)) * 100)
    fee = data.UPGRADE_FEE[card.rarity]
    await cb.answer()
    d = data.RARITIES[card.rarity]
    await edit_media(
        cb,
        None,
        f"{d['emoji']} {card.name}\nШанс успеха: {chance}%\nКомиссия: {fee:,} ФОчек\n"
        "⚠️ При неудаче жир исчезнет!\nУлучшаем?",
        ikb([[("✅ Улучшить", f"upgo:{card.id}"), ("❌ Отмена", "noop")]]),
    )


async def _do_single_upgrade(cb: CallbackQuery, session):
    card_id = int(cb.data.split(":")[1])
    card = await session.get(UserCard, card_id)
    if card is None or card.user_id != cb.from_user.id:
        await cb.answer("Жир не найден.", show_alert=True)
        return None
    if card.rarity == "mythic":
        await cb.answer("Легендарный жир улучшить нельзя!", show_alert=True)
        return None
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    fee = data.UPGRADE_FEE[card.rarity]
    if card.listed:
        await cb.answer("Жир выставлен на Авито.", show_alert=True)
        return None
    if user.points < fee:
        await cb.answer(f"Недостаточно ФОчек (нужно {fee:,}).", show_alert=True)
        return None
    user.points -= fee
    ok, new_card = await services.do_upgrade(session, user, card)
    achievements = await services.grant_achievements(session, user)
    return user, ok, new_card, achievements


@router.callback_query(lambda c: c.data and c.data.startswith("upgo:"))
async def cb_upgrade_one(cb: CallbackQuery, session):
    result = await _do_single_upgrade(cb, session)
    if result is None:
        return
    user, ok, new_card, achievements = result
    await cb.answer()
    if ok:
        d = data.RARITIES[new_card.rarity]
        text = (
            "🎉 Успех! Ваш жир стал лучше:\n"
            f"{d['emoji']} {new_card.name} · {d['name']} · {new_card.weight} кг\n"
            f"Цена: {fmt(new_card.base_price)} ФОчек"
        )
    else:
        text = "💥 Неудача! Жир не выдержал апгрейда и растворился…"
    if achievements:
        text += "\n\n🏆 " + "\n🏆 ".join(achievements)
    await edit_media(cb, None, text, None)


@router.message(Command("upgradeall"))
async def cmd_upgradeall(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    stats = await services.collection_stats(session, user.id)
    upgradable = {k: v for k, v in stats["by_rarity"].items() if k != "mythic"}
    if not upgradable:
        await message.answer("У вас нет жиров для улучшения.")
        return
    text = (
        f"@{user.username or user.id}\n"
        "🔥 Массовый апгрейд\nВыберите редкость жиров, которые хотите улучшить разом."
    )
    rows = []
    for key in data.ORDER[:-1]:
        cnt = upgradable.get(key, 0)
        if not cnt:
            continue
        d = data.RARITIES[key]
        fee = data.UPGRADE_FEE[key]
        rows.append([(f"{d['emoji']} {d['name']} [{cnt}] — {fee:,} за шт.", f"upar:{key}")])
    rows.append([("◀️ В меню", "noop")])
    await message.answer(text, reply_markup=ikb(rows))


@router.callback_query(lambda c: c.data and c.data.startswith("upar:"))
async def cb_upgrade_all(cb: CallbackQuery, session):
    rarity = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    cards = await _cards_of_rarity(session, user.id, rarity)
    if not cards:
        await cb.answer("Нет жиров этой редкости.", show_alert=True)
        return
    await cb.answer()
    fee = data.UPGRADE_FEE[rarity]
    upgraded, failed, skipped = [], 0, 0
    for card in cards:
        if card.listed or user.points < fee:
            skipped += 1
            continue
        user.points -= fee
        ok, new_card = await services.do_upgrade(session, user, card)
        if ok:
            upgraded.append(new_card)
        else:
            failed += 1
    achievements = await services.grant_achievements(session, user)
    parts = [f"🔥 Массовый апгрейд ({data.RARITIES[rarity]['name']}):"]
    if upgraded:
        names = ", ".join(f"{c.name} ({c.weight} кг)" for c in upgraded[:10])
        parts.append(f"✅ Улучшено: {len(upgraded)} — {names}")
    if failed:
        parts.append(f"💥 Провалено: {failed}")
    if skipped:
        parts.append(f"⏭ Пропущено: {skipped} (нет средств или на Авито)")
    if achievements:
        parts.append("🏆 " + "\n🏆 ".join(achievements))
    await edit_media(cb, None, "\n".join(parts), None)
