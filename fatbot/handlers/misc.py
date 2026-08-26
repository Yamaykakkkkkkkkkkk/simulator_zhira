import random

from aiogram import Router
from aiogram.types import CallbackQuery, Message

router = Router()


@router.callback_query(lambda c: c.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
