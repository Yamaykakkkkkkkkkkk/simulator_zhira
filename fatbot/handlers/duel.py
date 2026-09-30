from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import services

router = Router()


@router.message(Command("fduel"))
async def cmd_duel(message: Message, session):
    # AGENT3 QUESTS: засчитываем участие в дуэли (даже если игра в группах)
    try:
        user = await services.get_or_create_user(
            session, message.from_user.id, message.from_user.username, message.from_user.full_name
        )
        await services.update_quest_progress(session, user.id, "duel1", 1)
    except Exception:
        pass
    await message.answer("Дуэли доступны только в группах/чатах.")
