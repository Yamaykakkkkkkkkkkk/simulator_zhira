from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import services

router = Router()


@router.message(Command("roulette"))
async def cmd_roulette(message: Message, session):
    try:
        user = await services.get_or_create_user(
            session, message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        await services.update_quest_progress(session, user.id, "roulette1", 1)
    except Exception:
        pass
    text = (
        "Крутите рулетку в боте @fatroulettebot\n"
        'Команда: "рулетка", или "/roulette"'
    )
    await message.answer(text)
