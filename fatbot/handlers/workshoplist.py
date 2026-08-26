from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import services
from ..keyboards import ikb

router = Router()


@router.message(Command("workshoplist"))
async def cmd_workshoplist(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    workshops = await services.get_workshops(session, limit=10)

    lines = [
        f"@{user.username or user.id},",
        "🏭 Список мастерских:\n",
    ]
    if not workshops:
        lines.append("Пока нет мастерских. Будьте первым! /newworkshop")
    else:
        for i, w in enumerate(workshops, 1):
            rating = 5.0
            lines.append(
                f"{i}. 💸 Мастерская «{w.full_name or w.username}»\n"
                f"   Владелец: @{w.username or w.id}\n"
                f"   Уровень: {w.workshop_lvl} ⭐️\n"
            )

    kb = ikb([
        [("◀️ В меню", "noop")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)
