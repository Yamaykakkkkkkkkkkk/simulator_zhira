from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import confirm_kb, ikb
from ..utils import edit_media, fmt, remaining_str, utcnow

router = Router()


def daily_text(user) -> str:
    now = utcnow()
    lines = ["🎁 Ежедневный бонус", ""]
    day_next = (user.daily_day % 7) + 1
    for i, r in enumerate(data.DAILY_REWARDS, start=1):
        done = user.daily_day >= i and user.daily_last is not None
        mark = "✅" if (user.daily_day >= i and not (day_next == 1 and user.daily_day == 7)) else ("➡️" if i == day_next else "⬜️")
        fc = " +1 FC" if i == 7 else ""
        lines.append(f"{mark} День {i}: {fmt(r)} ФОчек{fc}")
    if user.daily_last is not None:
        elapsed = now - user.daily_last
        if elapsed.total_seconds() < 24 * 3600:
            lines.append(f"\n⏳ Следующий бонус через: {remaining_str(remaining(user.daily_last))}")
    return "\n".join(lines)


def remaining(last):
    from datetime import timedelta

    return (last + timedelta(hours=24)) - utcnow() if last else timedelta()


@router.message(Command("daily"))
@router.message(lambda m: m.text and m.text.strip().lower() in ("🎁 бонус", "бонус"))
async def cmd_daily(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    await message.answer(daily_text(user), reply_markup=confirm_kb("dly_go"))


@router.callback_query(lambda c: c.data == "dly_go")
async def cb_daily(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    result = await services.claim_daily(session, user)
    await cb.answer()
    if result is None:
        await edit_media(
            cb,
            None,
            f"⏳ Вы уже получали бонус сегодня.\nВозвращайтесь через {remaining_str(remaining(user.daily_last))}!",
            confirm_kb("dly_go"),
        )
        return
    day, reward, fc, completed, ref_msg = result
    text = f"✅ День {day}/7 — вы получили {fmt(reward)} ФОчек!" + (f" и {fc} F-Coin" if fc else "")
    if completed:
        text += "\n\n🎉 Цикл завершён! Цикл начнётся заново."
    if ref_msg:
        text += "\n\n" + ref_msg
    await edit_media(cb, None, text, confirm_kb("dly_go"))
