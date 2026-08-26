from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb, shop_kb
from ..models import Accessory
from ..utils import answer_media, edit_media, fmt
from sqlalchemy import select

router = Router()

EXCHANGE_COST = 1_000_000


@router.message(Command("fshop"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🛒 фшоп", "фшоп"))
async def cmd_fshop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    owned = await services.accessory_keys(session, user.id)
    lines = [
        "Добро пожаловать в ФШоп! 👜",
        "Здесь вы можете приобрести аксессуары за F-Coins.",
        "",
        f"💠 Ваши F-Coins: {user.fcoins}",
    ]
    for a in data.ACCESSORIES:
        mark = " ✅" if a["key"] in owned else ""
        lines.append(f"{a['emoji']} {a['name']} — {a['price']} FC{mark}\n   <i>{a['desc']}</i>")
    await answer_media(message, "shop", "\n".join(lines), shop_kb(owned))


@router.message(Command("finventory"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("💼 инвентарь", "инвентарь"))
async def cmd_inventory(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    keys = await services.accessory_keys(session, user.id)
    lines = [
        f"@{user.username or user.id},",
        "Добро пожаловать в инвентарь:\n",
    ]
    if not keys:
        lines.append("(пусто)")
    else:
        for k in keys:
            a = data.ACCESSORY_BY_KEY[k]
            lines.append(f"{a['emoji']} {a['name']} — {a['desc']}")
    lines.append(f"\n💠 F-Coins: {user.fcoins}")
    await answer_media(message, "inventory", "\n".join(lines))


@router.callback_query(lambda c: c.data and c.data.startswith("accbuy:"))
async def cb_accbuy(cb: CallbackQuery, session):
    key = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    acc = await services.buy_accessory(session, user, key)
    item = data.ACCESSORY_BY_KEY[key]
    if acc is None:
        if user.fcoins < item["price"]:
            await cb.answer(f"Недостаточно F-Coins (нужно {item['price']}).", show_alert=True)
        else:
            await cb.answer("Уже куплено.", show_alert=True)
        return
    await cb.answer(f"✅ Куплено: {item['name']}!")
    owned = await services.accessory_keys(session, user.id)
    await edit_media(cb, None, f"✅ {item['emoji']} {item['name']} теперь в вашем инвентаре!\n💠 Остаток: {user.fcoins} FC", shop_kb(owned))


@router.callback_query(lambda c: c.data == "accex")
async def cb_exchange(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    ok = await services.exchange_fcoin(session, user)
    await cb.answer()
    if ok:
        await edit_media(cb, None, f"🔁 Обмен успешен! Теперь у вас {user.fcoins} F-Coins.", shop_kb(await services.accessory_keys(session, user.id)))
    else:
        await cb.answer(f"Нужно минимум {EXCHANGE_COST:,} ФОчек.", show_alert=True)
