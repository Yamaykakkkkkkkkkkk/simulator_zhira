import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from ..filters import TextEquals
from ..keyboards import main_kb

router = Router()


@router.callback_query(lambda c: c.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(lambda c: c.data == "close")
async def cb_close(cb: CallbackQuery):
    try:
        if cb.message is not None:
            await cb.message.delete()
    except Exception:
        pass
    try:
        await cb.answer()
    except Exception:
        pass


@router.message(TextEquals("❌ скрыть", "скрыть"))
async def text_hide_keyboard(message: Message):
    await message.answer(
        "⌨️ Клавиатура скрыта. Чтобы вернуть кнопки — отправьте /menu.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(Command("menu"))
@router.message(TextEquals("📋 меню", "меню"))
async def cmd_menu(message: Message):
    await message.answer("⌨️ Кнопки возвращены!", reply_markup=main_kb())


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
