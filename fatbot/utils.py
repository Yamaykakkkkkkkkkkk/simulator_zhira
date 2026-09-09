import os
import random
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from textwrap import wrap

from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InputFile,
    FSInputFile,
    InputMediaPhoto,
    Message,
)
from PIL import Image, ImageDraw, ImageFont

from .config import ROOT

ASSETS = ROOT / "assets"

CARD_GRADIENT = {
    "common": ((70, 90, 120), (30, 40, 60)),
    "rare": ((30, 120, 90), (10, 50, 40)),
    "epic": ((120, 40, 160), (40, 10, 60)),
    "legendary": ((200, 150, 40), (120, 60, 10)),
    "mythic": ((220, 60, 40), (120, 10, 10)),
}


DEJAVU = ASSETS / "DejaVuSans.ttf"
DEJAVU_BOLD = ASSETS / "DejaVuSans-Bold.ttf"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = DEJAVU_BOLD if bold else DEJAVU
    return ImageFont.truetype(str(path), size)


def card_image(card) -> FSInputFile:
    top, bottom = CARD_GRADIENT.get(card.rarity, CARD_GRADIENT["common"])
    w, h = 900, 500
    img = Image.new("RGB", (w, h))
    dr = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        dr.line([(0, y), (w, y)], fill=color)

    d = {
        "common": {"name": "Ширпотреб", "emoji": "🥴"},
        "rare": {"name": "Домашний", "emoji": "🏠"},
        "epic": {"name": "Элитный", "emoji": "💎"},
        "legendary": {"name": "Ресторанный", "emoji": "👑"},
        "mythic": {"name": "Легендарный", "emoji": "🔥"},
    }[card.rarity]

    price_str = f"{card.base_price:,}"

    title_font = _font(52, bold=True)
    # NOTE: DejaVuSans has no color-emoji glyphs, so drawing rarity emoji
    # (🥴🏠💎👑🔥) with PIL produced tofu squares ("□"). Use DejaVu-safe
    # stars instead — they render on any platform.
    stars_font = _font(64, bold=True)
    sub_font = _font(34)
    price_font = _font(30)

    RARITY_STARS = {"common": 1, "rare": 2, "epic": 3, "legendary": 4, "mythic": 5}
    stars = "★" * RARITY_STARS.get(card.rarity, 1)

    def text_w(text, font):
        l, t, r, b = dr.textbbox((0, 0), text, font=font)
        return r - l

    stars_w = text_w(stars, stars_font)
    dr.text(((w - stars_w) / 2, 40), stars, fill=(255, 220, 120), font=stars_font)

    title = card.name
    for i, line in enumerate(wrap(title, 18)):
        line_w = text_w(line, title_font)
        dr.text(((w - line_w) / 2, 150 + i * 64), line, fill=(255, 255, 255), font=title_font)

    def center_text(text, font, y, fill=(255, 255, 255)):
        tw = text_w(text, font)
        dr.text(((w - tw) / 2, y), text, fill=fill, font=font)

    center_text(f"{d['name']} · {card.weight} кг", sub_font, 300, fill=(235, 235, 235))
    center_text(f"Цена: {price_str} ФОчек", price_font, 348, fill=(255, 220, 120))

    if getattr(card, "defects", None):
        center_text("Дефекты: " + ", ".join(card.defects), _font(24), 402, fill=(255, 160, 160))

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    return FSInputFile(path)


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
    ph = photo(key) if key and len(text) <= 1024 else None
    if ph:
        return await message.answer_photo(ph, caption=text, reply_markup=kb, parse_mode="HTML")
    return await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def edit_media(cb: CallbackQuery, key: str, text: str, kb: InlineKeyboardMarkup | None = None):
    if cb.message is None:
        return
    ph = photo(key) if key and len(text) <= 1024 else None
    has_photo = bool(getattr(cb.message, "photo", None))
    try:
        if ph and has_photo:
            await cb.message.edit_media(
                media=InputMediaPhoto(media=ph, caption=text, parse_mode="HTML"),
                reply_markup=kb,
            )
        elif not ph and not has_photo:
            await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            # Telegram cannot morph a photo message into a text one (or back)
            # via edit — replace it instead.
            try:
                await cb.message.delete()
            except Exception:
                pass
            if ph:
                await cb.message.answer_photo(ph, caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        try:
            if ph:
                await cb.message.answer_photo(ph, caption=text, reply_markup=kb, parse_mode="HTML")
            else:
                await cb.message.answer(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass
