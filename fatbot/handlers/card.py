import random

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import data, services
from ..filters import TextEquals
from ..keyboards import main_kb
from ..utils import answer_media, fmt, remaining_str, utcnow

router = Router()


def card_text(user, card, flavor, credited=True) -> str:
    d = data.RARITIES[card.rarity]
    lines = [
        f"@{user.username or user.id} Вам выпал жир!",
        f"{d['emoji']} {card.name}",
        f"{d['name']} | Цена: {fmt(card.base_price)} ФОчек",
        "",
        flavor,
    ]
    if card.defects:
        lines.append("Дефекты: " + ", ".join(card.defects))
    if credited:
        lines.append(f"\n💰 На баланс зачислено {fmt(card.base_price)} ФОчек.")
    return "\n".join(lines)


@router.message(Command("fcard"))
async def cmd_fcard(message: Message, session):
    await open_card(message, session)


@router.message(TextEquals("фкарточка", "фкарточку", "🐷 фкарточка", "жиркарточка"))
async def text_fcard(message: Message, session):
    await open_card(message, session)


async def open_card(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    now = utcnow()
    no_cooldown = await services.cooldown_disabled(session)
    if not no_cooldown:
        cd = await services.effective_cooldown(session, user)
        if user.next_card_at is not None and user.next_card_at > now:
            left = remaining_str(user.next_card_at - now)
            await message.answer(f"@{user.username or user.id}\nВы сможете выбить карточку еще раз через {left}.")
            return
    card, flavor, ref_msg = await services.roll_card(session, user)
    if not no_cooldown:
        user.next_card_at = now + cd
    user.points = (user.points or 0) + card.base_price
    achievements = await services.grant_achievements(session, user)
    text = card_text(user, card, flavor)
    if ref_msg:
        text += "\n\n" + ref_msg
    if achievements:
        text += "\n\n🏆 Новые достижения:\n" + "\n".join(achievements)
    await answer_media(message, "card", text)
