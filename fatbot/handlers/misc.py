import random

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from ..filters import TextEquals

router = Router()


@router.callback_query(lambda c: c.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.message(TextEquals("📦 контейнеры", "контейнеры"))
async def text_containers(message: Message, session):
    from .containers import cmd_mycontainers
    await cmd_mycontainers(message, session)


@router.message(TextEquals("🏭 ферма", "ферма"))
async def text_farm(message: Message, session):
    from .farm import cmd_farm
    await cmd_farm(message, session)


@router.message(TextEquals("📜 квесты", "квесты"))
async def text_quests(message: Message, session):
    from .quests import cmd_quests
    await cmd_quests(message, session)


@router.message(TextEquals("🛒 магазин жиров", "магазин жиров"))
async def text_fatshop(message: Message, session):
    from .fatshop import cmd_fatshop
    await cmd_fatshop(message, session)


@router.message(TextEquals("⚙️ настройки", "настройки"))
async def text_config(message: Message, session):
    from .config import cmd_config
    await cmd_config(message, session)
