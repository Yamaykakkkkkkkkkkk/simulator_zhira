import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InputFile, FSInputFile, Message

from .config import ROOT

ASSETS = ROOT / "assets"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fmt(n: int) -> str:
    return f"{n:,}"


def remaining_str(td: timedelta) -> str:
    total = max(0, int(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} ч")
    if m:
        parts.append(f"{m} мин")
    parts.append(f"{s} сек")
    return " ".join(parts)


def photo(key: str) -> InputFile | None:
    p = ASSETS / f"{key}.jpg"
    if p.exists():
        return FSInputFile(p)
    return None


async def answer_media(message: Message, key: str, text: str, kb: InlineKeyboardMarkup | None = None):
    ph = photo(key) if len(text) <= 1000 else None
    if ph:
        return await message.answer_photo(ph, caption=text, reply_markup=kb)
    return await message.answer(text, reply_markup=kb)


async def edit_media(cb: CallbackQuery, key: str, text: str, kb: InlineKeyboardMarkup | None = None):
    if cb.message is None:
        return
    ph = photo(key) if len(text) <= 1000 else None
    try:
        if ph and getattr(cb.message, "photo", None):
            await cb.message.edit_media(ph, caption=text)
            if kb:
                await cb.message.edit_reply_markup(reply_markup=kb)
        elif hasattr(cb.message, "edit_text"):
            await cb.message.edit_text(text, reply_markup=kb)
        else:
            await cb.message.answer(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.answer(text, reply_markup=kb)
        except Exception:
            pass
