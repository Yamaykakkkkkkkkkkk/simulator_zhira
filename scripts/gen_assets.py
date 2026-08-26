from PIL import Image, ImageDraw, ImageFont

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets"
OUT.mkdir(exist_ok=True)

W, H = 900, 500


def font(size=48):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make(name, c1, c2, emoji_big, title):
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    f_big = font(140)
    f_title = font(44)
    bbox = d.textbbox((0, 0), emoji_big, font=f_big)
    ew = bbox[2] - bbox[0]
    d.text(((W - ew) / 2, 90), emoji_big, font=f_big, fill=(255, 255, 255))
    bbox = d.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 330), title, font=f_title, fill=(255, 255, 255))
    img.save(OUT / f"{name}.jpg", quality=85)


make("welcome", (255, 140, 0), (120, 40, 140), "🐷", "СИМУЛЯТОР ЖИРА")
make("card", (70, 130, 180), (25, 25, 112), "🥓", "НОВЫЙ ЖИР")
make("collection", (60, 60, 60), (20, 20, 20), "🎒", "КОЛЛЕКЦИЯ")
make("profile", (34, 139, 34), (0, 60, 0), "👤", "ПРОФИЛЬ")
make("shop", (255, 105, 180), (80, 0, 80), "🛒", "ФШОП")
make("inventory", (105, 105, 105), (40, 40, 40), "💼", "ИНВЕНТАРЬ")
make("avito", (0, 191, 165), (0, 60, 50), "📢", "ЖИРОАВИТО")
make("upgradeshop", (255, 215, 0), (150, 80, 0), "⬆️", "УЛУЧШЕНИЯ")
print("OK:", OUT)
