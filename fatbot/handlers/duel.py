from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("fduel"))
async def cmd_duel(message: Message):
    await message.answer("Дуэли доступны только в группах/чатах.")
