from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from .. import data, services
from ..keyboards import ikb
from ..utils import edit_media, fmt

router = Router()


def _story_line(idx: int, qdef: dict | None, prog) -> str:
    total = len(data.STORY_QUESTS)
    if qdef is None:
        return f"🎉 Сюжет пройден полностью! ({total}/{total})\nВы — Легенда Жира! 🔥"
    p = f"{prog.progress}/{prog.target}" if prog else f"0/{qdef['target']}"
    fc = f" +{qdef.get('reward_fcoins')} FC" if qdef.get("reward_fcoins") else ""
    mark = "✅" if (prog and prog.completed and not prog.claimed) else ("🎁" if (prog and prog.claimed) else "⬜")
    return (
        f"📖 Сюжет {idx + 1}/{total}\n"
        f"{mark} {qdef['desc']} [{p}]\n"
        f"🎁 Награда: {fmt(qdef['reward'])} ФОчек{fc}"
    )


@router.message(Command("story"))
async def cmd_story(message: Message, session):
    user = await services.get_or_create_user(
        session, message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    idx, qdef, prog = await services.story_progress(session, user)
    total = len(data.STORY_QUESTS)
    lines = [f"@{user.username or user.id},", _story_line(idx, qdef, prog), ""]
    # показать следующие 2 шага для мотивации
    if qdef is not None:
        nxt = data.STORY_QUESTS[idx + 1: idx + 3]
        if nxt:
            lines.append("🔜 Далее:")
            for n in nxt:
                lines.append(f"  • {n['desc']} ({fmt(n['reward'])} ФОчек)")
    kb = ikb([
        [("📥 Забрать награду сюжета", "story_claim")],
        [("◀️ В меню", "noop")],
    ])
    await message.answer("\n".join(lines), reply_markup=kb)


@router.callback_query(lambda c: c.data == "story_claim")
async def cb_story_claim(cb: CallbackQuery, session):
    user = await services.get_or_create_user(session, cb.from_user.id, None, "")
    idx, qdef, prog = await services.story_progress(session, user)
    await cb.answer()
    if qdef is None:
        await edit_media(cb, None, "🎉 Сюжет уже пройден полностью!", None)
        return
    if prog is None or not prog.completed:
        p = f"{prog.progress}/{prog.target}" if prog else f"0/{qdef['target']}"
        await edit_media(cb, None, f"❌ Шаг ещё не выполнен! Прогресс: {p}\n{qdef['desc']}", None)
        return
    if prog.claimed:
        await edit_media(cb, None, "✅ Награда уже получена!", None)
        return
    claimed = await services.claim_story(session, user.id)
    if claimed is None:
        await edit_media(cb, None, "❌ Не удалось забрать награду.", None)
        return
    fc = f" +{claimed.get('reward_fcoins')} FC" if claimed.get("reward_fcoins") else ""
    await edit_media(cb, None, f"✅ Сюжет {idx + 1} пройден!\n💰 +{fmt(claimed['reward'])} ФОчек{fc}!\n\nСледующий: /story", None)
