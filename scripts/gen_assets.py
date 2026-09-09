from PIL import Image, ImageDraw, ImageFont

import os
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets"
OUT.mkdir(exist_ok=True)

W, H = 900, 500


def font(size=48):
    # 1. Bundled repo fonts — work on Windows and Linux, include Cyrillic.
    for p in (OUT / "DejaVuSans-Bold.ttf", OUT / "DejaVuSans.ttf"):
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    # 2. System DejaVu (Linux).
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    # 3. Windows Arial (has Cyrillic).
    for p in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make(name, c1, c2, emoji_big, title):
    _ = emoji_big  # intentionally unused: DejaVu has no color-emoji glyphs,
    # drawing emoji with PIL produced tofu squares ("□") on every banner.
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    # Decorative outline circles (font-independent, can never become tofu).
    d.ellipse([-140, -140, 140, 140], outline=(255, 255, 255), width=6)
    d.ellipse([W - 140, H - 140, W + 140, H + 140], outline=(255, 255, 255), width=6)
    d.ellipse([-70, -70, 70, 70], outline=(255, 255, 255), width=3)
    f_title = font(54)
    f_sub = font(30)
    bbox = d.textbbox((0, 0), title, font=f_title)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 200), title, font=f_title, fill=(255, 255, 255))
    # Thin underline bar under the title.
    bar_w = min(320, max(120, tw // 2))
    d.rounded_rectangle(
        [(W - bar_w) / 2, 290, (W + bar_w) / 2, 298],
        radius=4,
        fill=(255, 255, 255),
    )
    sub = "СИМУЛЯТОР ЖИРА" if name != "welcome" else "ИГРА ПРО ЖИР • F-COINS • АВИТО"
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    sw = bbox[2] - bbox[0]
    d.text(((W - sw) / 2, 320), sub, font=f_sub, fill=(235, 235, 235))
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
