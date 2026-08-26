from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import answer_media, edit_media, fmt

router = Router()


@router.message(Command("ffarm"))
async def cmd_farm(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    farm = await services.get_farm(session, user.id)

    if farm is None:
        text = (
            f"@{user.username or user.id}\n"
            "У вас пока нет фермы. Создайте её за 500,000 ФОчек!"
        )
        kb = ikb([
            [("🏭 Создать ферму (500,000 ФОчек)", "farm_create")],
            [("◀️ В меню", "noop")],
        ])
        await message.answer(text, reply_markup=kb)
        return

    psu_power = data.FARM_POWER.get(farm.psu_lvl, 50)
    cooling = data.FARM_COOLING.get(farm.cooling_lvl, 45)
    slots = data.FARM_SLOTS.get(farm.rack_lvl, 2)
    fcoin_rate = data.FARM_FCOIN_PER_HOUR.get(farm.rack_lvl, 5)

    status = "✅ Работает" if farm.is_running else "🛑 Выключена"

    lines = [
        f"@{user.username or user.id}, Ваша модульная ферма:\n",
        f"Состояние: {status}",
        f"🔋 Питание (PSU ур.{farm.psu_lvl}): {farm.power_used}/{psu_power} W",
        f"🌡 Охлаждение (Cooling ур.{farm.cooling_lvl}): {farm.heat_used}/{cooling} TDP",
        f"\n💻 Слоты (Rack ур.{farm.rack_lvl}):",
    ]

    for i in range(1, slots + 1):
        card_id = getattr(farm, f"slot{i}_card", None)
        if card_id:
            lines.append(f"  {i}. 🐷 Слот занят")
        else:
            lines.append(f"  {i}. 💨 Пусто")

    lines.append(f"\n💰 Баланс: {farm.fcoins_balance} / {fcoin_rate} F-Coins/час")

    kb = ikb([
        [("▶️ Включить" if not farm.is_running else "⏸ Выключить", "farm_toggle")],
        [("⬆️ Улучшить PSU", f"farm_upg:psu"), ("⬆️ Улучшить Cooling", f"farm_upg:cooling")],
        [("⬆️ Улучшить Rack", f"farm_upg:rack"), ("💰 Собрать", "farm_collect")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(lambda c: c.data == "farm_create")
async def cb_farm_create(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    farm, error = await services.create_farm(session, user.id, 500_000)
    await cb.answer()
    if error:
        await edit_media(cb, None, f"❌ {error}", None)
        return
    await edit_media(cb, None, "🏭 Ферма создана! Теперь настройте и включите её.", None)


@router.callback_query(lambda c: c.data == "farm_toggle")
async def cb_farm_toggle(cb: CallbackQuery, session):
    farm = await services.get_farm(session, cb.from_user.id)
    if farm is None:
        await cb.answer("Ферма не найдена.", show_alert=True)
        return
    farm.is_running = not farm.is_running
    status = "включена" if farm.is_running else "выключена"
    await cb.answer()
    await edit_media(cb, None, f"🏭 Ферма {status}.", None)
