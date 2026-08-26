from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import services
from ..models import User
from ..utils import fmt

router = Router()

PAY_USAGE = (
    "Использование:\n"
    "1. Ответом на сообщение: /pay <сумма> [комментарий]\n"
    "2. По юзернейму: /pay @username <сумма> [комментарий]\n"
    "3. По ID: /pay <user_id> <сумма> [комментарий]\n\n"
    "💡 Подсказка: Сумму можно писать с буквами 'к' (тысяча) и 'кк' (миллион)."
)

PAYCOIN_USAGE = (
    "Использование: /paycoin <@юзернейм или ID получателя> <количество>\n"
    "Пример: /paycoin @testuser 10\n"
    "Пример: /paycoin 123456789 5"
)


async def _resolve_target(session, message, target_raw: str) -> User | None:
    if target_raw.startswith("@"):
        return await services.get_by_username(session, target_raw)
    if target_raw.isdigit():
        return await session.get(User, int(target_raw))
    return None


@router.message(Command("pay"))
async def cmd_pay(message: Message, session):
    me = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    parts = (message.text or "").split()
    comment = []
    target = None
    amount = None

    if message.reply_to_message is not None:
        for p in parts[1:]:
            parsed = services.parse_amount(p)
            if parsed is not None:
                amount = parsed
                continue
            comment.append(p)
        target = await services.get_or_create_user(
            session,
            message.reply_to_message.from_user.id,
            message.reply_to_message.from_user.username,
            message.reply_to_message.from_user.full_name,
        )
    else:
        if len(parts) < 3:
            await message.answer(PAY_USAGE)
            return
        target = await _resolve_target(session, message, parts[1])
        amount = services.parse_amount(parts[2])
        comment = parts[3:]

    if target is None:
        await message.answer("❌ Получатель не найден. Возможно, он ещё не запускал бота.")
        return
    if amount is None:
        await message.answer(PAY_USAGE)
        return
    try:
        await services.transfer_points(session, me, target, amount)
    except ValueError as e:
        await message.answer(f"❌ {e}")
        return
    suffix = f" 💬 {' '.join(comment)}" if comment else ""
    await message.answer(f"✅ Вы перевели {fmt(amount)} ФОчек игроку @{target.username or target.id}.{suffix}")


@router.message(Command("paycoin"))
async def cmd_paycoin(message: Message, session):
    me = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(PAYCOIN_USAGE)
        return
    try:
        amount = int(parts[2])
    except ValueError:
        await message.answer(PAYCOIN_USAGE)
        return
    target = await _resolve_target(session, message, parts[1])
    if target is None:
        await message.answer("❌ Получатель не найден.")
        return
    if target.id == me.id:
        await message.answer("❌ Нельзя переводить самому себе.")
        return
    if amount <= 0:
        await message.answer("❌ Количество должно быть больше нуля.")
        return
    if me.fcoins < amount:
        await message.answer("❌ Недостаточно F-Coins.")
        return
    me.fcoins -= amount
    target.fcoins += amount
    await message.answer(f"✅ Вы перевели {amount} F-Coins игроку @{target.username or target.id}.")
