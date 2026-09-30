from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import answer_media, edit_media, fmt

router = Router()


def prestige_text(user) -> str:
    ok, reason = services.prestige_available(user)
    bonus = int(round((services.prestige_bonus(user) - 1.0) * 100))
    lines = [
        f"@{user.username or user.id}, 🌟 Престиж (перерождение)",
        "",
        f"🏆 Текущий престиж: {user.prestige_lvl or 0} (вечный бонус к доходу: +{bonus}%)",
        f"💰 Баланс: {fmt(user.points or 0)} / {fmt(data.PRESTIGE_POINTS_REQ)} ФОчек",
        f"🐷 Открыто жиров: {user.cards_opened or 0} / {data.PRESTIGE_CARDS_REQ}",
        "",
        "Перерождение обнуляет ФОчки, счётчик жиров и все ветки прокачки,",
        f"но даёт {int(data.PRESTIGE_INCOME_PER_LVL * 100)}% к доходу НАВСЕГДА за каждый уровень.",
    ]
    if not ok:
        lines += ["", f"❌ {reason}"]
    return "\n".join(lines)


def prestige_kb(user):
    ok, _ = services.prestige_available(user)
    rows = []
    if ok:
        rows.append([("🌟 ПЕРЕРОДИТЬСЯ", "prestige_go")])
    return ikb(rows)


@router.message(Command("prestige"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🌟 престиж", "престиж", "перерождение"))
async def cmd_prestige(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    await answer_media(message, "prestige", prestige_text(user), prestige_kb(user))


@router.callback_query(lambda c: c.data == "prestige_go")
async def cb_prestige_go(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    ok, msg = await services.do_prestige(session, user)
    await cb.answer()
    await edit_media(cb, None, (("🎉 " if ok else "❌ ") + msg), prestige_kb(user))
