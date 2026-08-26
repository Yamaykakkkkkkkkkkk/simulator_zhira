from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import answer_media, edit_media, fmt

router = Router()


@router.message(Command("fcontainershop"))
async def cmd_containershop(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    containers = await services.get_containers(session, user.id)
    capacity = await services.total_container_capacity(session, user.id)

    text = (
        f"Добро пожаловать в магазин контейнеров! 📦\n"
        "Здесь вы можете приобрести контейнеры за ФОчки.\n\n"
        f"📦 У вас: {len(containers)}/{data.MAX_CONTAINERS} контейнеров\n"
        f"📁 Общая вместимость: {capacity} жиров\n\n"
        "Выберите тип контейнера:"
    )
    rows = []
    for c in data.CONTAINER_TYPES:
        label = f"{c['emoji']} {c['name']} — {fmt(c['price'])} ФОчек ({c['capacity']} слотов)"
        rows.append([(label, f"buy_cont:{c['key']}")])
    rows.append([("◀️ В меню", "noop")])
    await message.answer(text, reply_markup=ikb(rows))


@router.callback_query(lambda c: c.data and c.data.startswith("buy_cont:"))
async def cb_buy_container(cb: CallbackQuery, session):
    ctype = cb.data.split(":")[1]
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    container, error = await services.buy_container(session, user.id, ctype)
    await cb.answer()
    if error:
        await edit_media(cb, None, f"❌ {error}", None)
        return
    item = data.CONTAINER_BY_KEY[ctype]
    await edit_media(
        cb,
        None,
        f"✅ Куплен контейнер: {item['emoji']} {item['name']}\n"
        f"Вместимость: +{item['capacity']} слотов\n"
        f"💰 Остаток: {fmt(user.points)} ФОчек",
        None,
    )


@router.message(Command("mycontainers"))
async def cmd_mycontainers(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    containers = await services.get_containers(session, user.id)
    capacity = await services.total_container_capacity(session, user.id)
    stats = await services.collection_stats(session, user.id)

    lines = [
        f"@{user.username or user.id},",
        f"📦 Ваши контейнеры: {len(containers)}/{data.MAX_CONTAINERS}\n",
    ]
    if not containers:
        lines.append("У вас пока нет контейнеров (Вместимость: 0). Вы можете приобрести их в магазине!")
    else:
        for c in containers:
            item = data.CONTAINER_BY_KEY.get(c.ctype, {"name": "Неизвестный", "emoji": "❓"})
            lines.append(f"{item['emoji']} {item['name']} — {c.capacity} слотов")
        lines.append(f"\n📁 Общая вместимость: {capacity} жиров")
        lines.append(f"🃏 Жиров в коллекции: {stats['count']}")

    kb = ikb([
        [("🛒 Купить контейнер", "contshop_short")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(lambda c: c.data == "contshop_short")
async def cb_contshop_short(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    text = "📦 Магазин контейнеров:"
    rows = []
    for c in data.CONTAINER_TYPES:
        label = f"{c['emoji']} {c['name']} — {fmt(c['price'])} ФОчек"
        rows.append([(label, f"buy_cont:{c['key']}")])
    rows.append([("◀️ Назад", "cont_back")])
    await cb.answer()
    await edit_media(cb, None, text, ikb(rows))


@router.callback_query(lambda c: c.data == "cont_back")
async def cb_cont_back(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    containers = await services.get_containers(session, user.id)
    capacity = await services.total_container_capacity(session, user.id)
    lines = [f"📦 Ваши контейнеры: {len(containers)}/{data.MAX_CONTAINERS}", f"📁 Вместимость: {capacity}"]
    kb = ikb([
        [("🛒 Купить контейнер", "contshop_short")],
        [("◀️ В меню", "noop")],
    ])
    await cb.answer()
    await edit_media(cb, None, "\n".join(lines), kb)
