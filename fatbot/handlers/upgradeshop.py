from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb, upgrades_kb
from ..utils import answer_media, edit_media, fmt

router = Router()


@router.message(Command("upgradeshop"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("⬆️ улучшения", "улучшения"))
async def cmd_upgradeshop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    lines = [
        f"@{user.username or user.id}",
        "Добро пожаловать в магазин улучшений!",
        "",
        "Выберите, что хотите прокачать:",
        f"💰 Баланс: {fmt(user.points)} ФОчек",
    ]
    for u in data.UPGRADES:
        lvl = getattr(user, f"{u['key']}_lvl")
        cost = "MAX" if lvl >= data.UPGRADE_MAX_LVL else f"{data.UPGRADE_COST(lvl):,}"
        lines.append(f"{u['emoji']} {u['name']} [{lvl}/{data.UPGRADE_MAX_LVL}] — следующее: {cost}\n   {u['desc']}")
    await answer_media(message, "upgradeshop", "\n".join(lines), upgrades_kb(user))


@router.callback_query(lambda c: c.data and c.data.startswith("ubuy:"))
async def cb_ubuy(cb: CallbackQuery, session):
    key = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    ok = await services.buy_upgrade_level(session, user, key)
    u = next(x for x in data.UPGRADES if x["key"] == key)
    lvl = getattr(user, f"{key}_lvl")
    await cb.answer()
    if ok:
        text = (
            f"✅ {u['emoji']} {u['name']} прокачано до уровня {lvl}!\n"
            f"💰 Баланс: {fmt(user.points)} ФОчек"
        )
        await edit_media(cb, None, text, upgrades_kb(user))
    else:
        if lvl >= data.UPGRADE_MAX_LVL:
            await cb.answer("Максимальный уровень!", show_alert=True)
        else:
            need = data.UPGRADE_COST(lvl)
            await cb.answer(f"Недостаточно ФОчек (нужно {need:,}).", show_alert=True)
