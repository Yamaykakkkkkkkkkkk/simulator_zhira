from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media, fmt

router = Router()


def farm_status_text(user, farm) -> str:
    level_data = next((l for l in data.FARM_LEVELS if l["lvl"] == farm.level), data.FARM_LEVELS[0])
    slots_used = services.farm_slots_used(farm)
    max_slots = services.farm_max_slots(farm)
    cal_per_hour = services.farm_calories_per_hour(farm)
    pending = services.farm_pending_points(farm)

    status = "✅ Работает" if farm.is_running else "🛑 Выключена"

    lines = [
        f"@{user.username or user.id}, Ваша столовая:\n",
        f"📋 Уровень: {level_data['name']} (ур. {farm.level})",
        f"🍳 Состояние: {status}\n",
        f"📊 Эффективность: x{level_data['efficiency']}",
        f"📈 Калорий в час: {cal_per_hour}",
        f"💰 К сбору: {fmt(pending)} ФОчек\n",
        f"🍽 Слоты: {slots_used}/{max_slots}\n",
    ]

    for i in range(1, max_slots + 1):
        product_key = getattr(farm, f"slot{i}_product", None)
        if product_key and product_key in data.FARM_PRODUCTS_BY_KEY:
            p = data.FARM_PRODUCTS_BY_KEY[product_key]
            lines.append(f"  {i}. {p['emoji']} {p['name']} — {p['calories']} кал/час")
        else:
            lines.append(f"  {i}. 💨 Пусто")

    return "\n".join(lines)


@router.message(Command("ffarm"))
async def cmd_farm(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    farm = await services.get_farm(session, user.id)

    if farm is None:
        text = (
            f"@{user.username or user.id}\n"
            "У вас пока нет столовой. Создайте её за 500,000 ФОчек!\n\n"
            "🍳 Столовая — это место, где вы готовите еду.\n"
            "Еда даёт калории, которые превращаются в ФОчки."
        )
        kb = ikb([
            [("🍳 Создать столовую (500,000 ФОчек)", "farm_create")],
            [("◀️ В меню", "noop")],
        ])
        await message.answer(text, reply_markup=kb)
        return

    text = farm_status_text(user, farm)
    kb = ikb([
        [("▶️ Включить" if not farm.is_running else "⏸ Выключить", "farm_toggle")],
        [("🍽 Добавить еду", "farm_add_food"), ("💰 Собрать", "farm_collect")],
        [("⬆️ Улучшить столовую", "farm_upgrade")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(lambda c: c.data == "farm_create")
async def cb_farm_create(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    farm, error = await services.create_farm(session, user.id, 500_000)
    await cb.answer()
    if error:
        await edit_media(cb, None, f"❌ {error}", None)
        return
    await edit_media(cb, None, "🍳 Столовая создана! Теперь добавьте еду и включите её.", None)


@router.callback_query(lambda c: c.data == "farm_toggle")
async def cb_farm_toggle(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    cal = services.farm_calories_per_hour(farm)
    if not farm.is_running and cal == 0:
        await cb.answer("Добавьте еду в слоты перед включением!", show_alert=True)
        return

    farm.is_running = not farm.is_running
    status = "включена" if farm.is_running else "выключена"
    await cb.answer()

    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    text = farm_status_text(user, farm)
    await edit_media(cb, None, f"🍳 Столовая {status}!\n\n{text}", None)


@router.callback_query(lambda c: c.data == "farm_collect")
async def cb_farm_collect(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    amount = await services.farm_collect(session, farm)
    await cb.answer()
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")

    if amount > 0:
        text = f"💰 Собрано {fmt(amount)} ФОчек!\n\n{farm_status_text(user, farm)}"
    else:
        text = f"Пока нечего собирать. Включите столовую и подождите.\n\n{farm_status_text(user, farm)}"

    kb = ikb([
        [("▶️ Включить" if not farm.is_running else "⏸ Выключить", "farm_toggle")],
        [("🍽 Добавить еду", "farm_add_food"), ("💰 Собрать", "farm_collect")],
        [("⬆️ Улучшить столовую", "farm_upgrade")],
        [("◀️ В меню", "noop")],
    ])
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data == "farm_add_food")
async def cb_farm_add_food(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    max_slots = services.farm_max_slots(farm)
    used_slots = services.farm_slots_used(farm)

    if used_slots >= max_slots:
        await cb.answer("Все слоты заняты! Уберите еду или улучшите столовую.", show_alert=True)
        return

    lines = ["🍽 Выберите блюдо для добавления:\n"]
    rows = []
    for p in data.FARM_PRODUCTS:
        label = f"{p['emoji']} {p['name']} — {fmt(p['price'])} ФОчек ({p['calories']} кал/час)"
        rows.append([(label, f"farm_place:{p['key']}")])
    rows.append([("◀️ Назад", "farm_back")])

    await cb.answer()
    await edit_media(cb, None, "\n".join(lines), ikb(rows))


@router.callback_query(lambda c: c.data and c.data.startswith("farm_place:"))
async def cb_farm_place(cb: CallbackQuery, session):
    product_key = cb.data.split(":")[1]
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    max_slots = services.farm_max_slots(farm)
    product = data.FARM_PRODUCTS_BY_KEY.get(product_key)
    if not product:
        await cb.answer("Блюдо не найдено.", show_alert=True)
        return

    needed_slots = product["slot"]
    free_slots = max_slots - services.farm_slots_used(farm)
    if needed_slots > free_slots:
        await cb.answer(f"Нужно {needed_slots} слотов, свободно {free_slots}.", show_alert=True)
        return

    slot = None
    for i in range(1, max_slots + 1):
        if not getattr(farm, f"slot{i}_product", None):
            slot = i
            break

    if slot is None:
        await cb.answer("Нет свободных слотов.", show_alert=True)
        return

    ok, error = await services.place_food_in_slot(session, farm, slot, product_key)
    if not ok:
        await cb.answer(error, show_alert=True)
        return

    await cb.answer()
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    text = farm_status_text(user, farm)
    await edit_media(cb, None, f"✅ {product['emoji']} {product['name']} установлено в слот {slot}!\n\n{text}", None)


@router.callback_query(lambda c: c.data == "farm_upgrade")
async def cb_farm_upgrade(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    if farm.level >= 3:
        await cb.answer("Максимальный уровень!", show_alert=True)
        return

    next_level = next((l for l in data.FARM_LEVELS if l["lvl"] == farm.level + 1), None)
    if not next_level:
        await cb.answer("Максимальный уровень!", show_alert=True)
        return

    text = (
        f"⬆️ Улучшение столовой\n\n"
        f"Текущий: {data.FARM_LEVELS[farm.level-1]['name']} (ур. {farm.level})\n"
        f"Следующий: {next_level['name']} (ур. {next_level['lvl']})\n"
        f"Слоты: {next_level['slots']} (было {services.farm_max_slots(farm)})\n"
        f"Эффективность: x{next_level['efficiency']} (было x{data.FARM_LEVELS[farm.level-1]['efficiency']})\n\n"
        f"💰 Стоимость: {fmt(next_level['upgrade_cost'])} ФОчек"
    )
    kb = ikb([
        [(f"✅ Улучшить за {fmt(next_level['upgrade_cost'])} ФОчек", "farm_do_upgrade")],
        [("◀️ Назад", "farm_back")],
    ])
    await cb.answer()
    await edit_media(cb, None, text, kb)


@router.callback_query(lambda c: c.data == "farm_do_upgrade")
async def cb_farm_do_upgrade(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Столовая не найдена.", show_alert=True)
        return

    ok, error = await services.upgrade_farm(session, farm)
    if not ok:
        await cb.answer(error, show_alert=True)
        return

    await cb.answer("✅ Столовая улучшена!")
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    text = farm_status_text(user, farm)
    await edit_media(cb, None, f"🎉 Столовая улучшена!\n\n{text}", None)


@router.callback_query(lambda c: c.data == "farm_back")
async def cb_farm_back(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await edit_media(cb, None, "Столовая не найдена.", None)
        return

    text = farm_status_text(user, farm)
    kb = ikb([
        [("▶️ Включить" if not farm.is_running else "⏸ Выключить", "farm_toggle")],
        [("🍽 Добавить еду", "farm_add_food"), ("💰 Собрать", "farm_collect")],
        [("⬆️ Улучшить столовую", "farm_upgrade")],
        [("◀️ В меню", "noop")],
    ])
    await cb.answer()
    await edit_media(cb, None, text, kb)
