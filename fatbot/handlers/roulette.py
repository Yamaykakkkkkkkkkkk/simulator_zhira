from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("roulette"))
async def cmd_roulette(message: Message):
    text = (
        "Крутите рулетку в боте @fatroulettebot\n"
        'Команда: "рулетка", или "/roulette"'
    )
    await message.answer(text)
