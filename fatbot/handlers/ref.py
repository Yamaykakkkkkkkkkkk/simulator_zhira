from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import data, services
from ..config import BOT_USERNAME
from ..models import Referral
from sqlalchemy import func, select

router = Router()


@router.message(Command("ref"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🤝 рефералы", "рефералы"))
async def cmd_ref(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    invited = (
        await session.scalar(select(func.count()).select_from(select(Referral).where(Referral.referrer_id == user.id).subquery()))
    ) or 0
    text = (
        f"@{user.username or user.id}, Ваша реферальная ссылка:\n\n"
        f"🔗 https://t.me/{BOT_USERNAME}?start={user.id}\n\n"
        "Приглашайте друзей и зарабатывайте вместе!\n"
        "Бонусы за активность приглашенных:\n\n"
        "🔹 50,000 ФОчек каждому — когда друг откроет 3 карточки.\n"
        "🔹 100,000 ФОчек каждому — когда друг завершит 7-дневный цикл ежедневных наград.\n\n"
        f"👥 Вы уже пригласили: {invited}"
    )
    await message.answer(text)
