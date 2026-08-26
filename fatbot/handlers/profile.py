from sqlalchemy import select

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import data, services
from ..models import ProfileView, User
from ..utils import answer_media, fmt

router = Router()


async def account_text(session, user: User) -> str:
    stats = await services.collection_stats(session, user.id)
    views = await services.views_count(session, user.id)
    ach_count = len((await session.scalars(_ach_q(user.id))).all())
    return (
        f"👤 Профиль: @{user.username or user.id}\n\n"
        f"📈 Статус: {services.status_name(stats['weight'])}\n"
        f"💰 ФОчки: {fmt(user.points)}\n"
        f"💠 F-Coins: {user.fcoins}\n"
        f"🐷 Общая стоимость жиров: {fmt(stats['value'])} ФОчек\n"
        f"⚖️ Общий вес жиров: {fmt(stats['weight'])} кг\n"
        f"🃏 Жиров в коллекции: {stats['count']}\n"
        f"🏆 Выполнено достижений: {ach_count}\n"
        f"👁 Ваш профиль просмотрело {views} игроков."
    )


def _ach_q(user_id):
    from ..models import Achievement

    return select(Achievement).where(Achievement.user_id == user_id)


@router.message(Command("faccount", "profile", "account"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("👤 профиль", "профиль"))
async def cmd_profile(message: Message, session):
    me = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    parts = (message.text or "").split()
    target = None
    if len(parts) >= 2:
        raw = parts[1]
        if raw.startswith("@"):
            target = await services.get_by_username(session, raw)
        elif raw.isdigit():
            target = await session.get(User, int(raw))
        if target is None:
            await message.answer("❌ Игрок не найден.")
            return
    else:
        target = me
    if target.id != me.id:
        session.add(ProfileView(viewer_id=me.id, target_id=target.id))
        await grant_view_achievement(session, target)
    text = await account_text(session, target)
    if target.id != me.id:
        text += "\n\n👁 Вы посмотрели профиль этого игрока."
    await answer_media(message, "profile", text)


async def grant_view_achievement(session, target):
    await services.grant_achievements(session, target)
