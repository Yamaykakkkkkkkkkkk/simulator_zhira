from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media

router = Router()


@router.message(Command("achievements"))
async def cmd_achievements(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    catalog = await services.get_achievements_catalog(session, user.id)

    lines = [
        f"@{user.username or user.id}, Добро пожаловать в каталог достижений!\n",
        "Выберите нужный раздел:\n",
    ]
    owned = [a for a in catalog if a["owned"]]
    unowned = [a for a in catalog if not a["owned"]]

    if owned:
        lines.append("✅ Полученные:")
        for a in owned:
            lines.append(f"  {a['title']}")
    if unowned:
        lines.append("\n🔒 Неполученные:")
        for a in unowned:
            lines.append(f"  {a['title']}")

    kb = ikb([
        [("📋 Все достижения", "ach_all")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(lambda c: c.data == "ach_all")
async def cb_achievements_all(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    catalog = await services.get_achievements_catalog(session, user.id)

    lines = ["📋 Все достижения:\n"]
    for a in catalog:
        mark = "✅" if a["owned"] else "🔒"
        lines.append(f"{mark} {a['title']}")

    await cb.answer()
    await edit_media(cb, None, "\n".join(lines), None)
