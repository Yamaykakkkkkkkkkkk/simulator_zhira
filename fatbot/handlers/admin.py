from sqlalchemy import update

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import services
from ..config import ADMIN_IDS, OWNER_ID
from ..models import User

router = Router()


@router.message(Command("fcooldown"))
async def cmd_fcooldown(message: Message, session):
    if message.from_user.id != OWNER_ID:
        return
    disabled = await services.cooldown_disabled(session)
    new_state = not disabled
    await services.set_setting(session, "no_cooldown", "1" if new_state else "0")
    if new_state:
        await session.execute(update(User).values(next_card_at=None))
        await message.answer(
            "✅ Задержка карточек глобально отключена!\n"
            "🐷 Теперь все игроки могут выбивать жиров без ограничений.\n"
            "Повторный вызов /fcooldown включит задержку обратно."
        )
    else:
        await message.answer(
            "⏳ Задержка карточек глобально включена обратно.\n"
            "🐷 Стандартный кулдаун снова действует для всех игроков."
        )


@router.message(Command("give"))
async def cmd_give(message: Message, session):
    if message.from_user.id not in ADMIN_IDS:
        return
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer("Использование: /give <id|@username> <сумма> | /give <id|@username> fc:<кол-во>")
        return
    raw = parts[1]
    if raw.startswith("@"):
        target = await services.get_by_username(session, raw)
    elif raw.isdigit():
        target = await session.get(User, int(raw))
    else:
        target = None
    if target is None:
        await message.answer("❌ Игрок не найден.")
        return
    spec = parts[2]
    if spec.lower().startswith("fc:"):
        amount = int(spec[3:])
        target.fcoins += amount
        await message.answer(f"✅ Начислено {amount} F-Coins игроку @{target.username or target.id}.")
    else:
        from ..services import parse_amount

        amount = parse_amount(spec)
        if not amount:
            await message.answer("❌ Неверная сумма.")
            return
        target.points += amount
        await message.answer(f"✅ Начислено {amount:,} ФОчек игроку @{target.username or target.id}.")
